"""
pages/2_Library.py — Browse, process, and annotate everything you've captured.

Each card now has three sections beyond the basic content:

  AI Insights     — summary + actionable insight, generated on demand.
                    "Process with AI" runs the model and saves results to DB.
                    Suggested tags and related items appear immediately after
                    processing and can be applied with one click.

  Your Take       — impact rating (1-5) + synthesis note. Saved separately
                    from AI processing so you can rate anything without AI.

  Manage          — Delete with confirmation.

Performance: one DB connection is opened at the top to load all display data
(items, highlights, tags). Button handlers open their own short-lived
connections for writes, then call st.rerun().
"""

import streamlit as st

from ai import process_item, process_highlight
from database import (
    add_item_link,
    apply_suggested_tags_to_highlight,
    apply_suggested_tags_to_item,
    delete_highlight,
    delete_item,
    delete_item_link,
    get_all_tags,
    get_conn,
    get_content_types,
    get_highlight_tags,
    get_highlights,
    get_item_links,
    get_item_tags,
    get_items,
    get_library_for_ai_context,
    get_tag_related_items,
    get_tags_for_highlights_batch,
    get_tags_for_items_batch,
    init_db,
    update_highlight_ai,
    update_highlight_rating,
    update_item_ai,
    update_item_rating,
)
from utils import format_date, item_to_markdown, safe_filename

st.set_page_config(page_title="Library", layout="wide")

init_db()

st.title("Library")
st.caption("Everything you've captured — browse, process, and annotate.")

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Search & Filter")

    search = st.text_input("Search", placeholder="keyword...", key="lib_search")

    conn = get_conn()
    content_types = get_content_types(conn)
    all_tags = get_all_tags(conn)
    conn.close()

    ct_options = {"All types": None}
    for ct in content_types:
        ct_options[ct["name"]] = ct["id"]

    selected_ct_label = st.selectbox(
        "Content type",
        list(ct_options.keys()),
        key="lib_ct",
        help="Applies to Items tab only.",
    )
    selected_ct_id = ct_options[selected_ct_label]

    tag_opts = ["All tags"] + all_tags
    selected_tag_label = st.selectbox("Tag", tag_opts, key="lib_tag")
    selected_tag = None if selected_tag_label == "All tags" else selected_tag_label

    st.markdown("---")
    if st.button("Clear filters", key="clear_filters"):
        for k in ["lib_search", "lib_ct", "lib_tag"]:
            st.session_state.pop(k, None)
        st.rerun()

# ─── Load all display data (one connection, all batch queries) ────────────────

conn = get_conn()

items = get_items(
    conn,
    search=search or None,
    content_type_id=selected_ct_id,
    tag=selected_tag,
)
highlights = get_highlights(
    conn,
    search=search or None,
    tag=selected_tag,
)

item_ids = [i["id"] for i in items]
highlight_ids = [h["id"] for h in highlights]
item_tags_map = get_tags_for_items_batch(conn, item_ids)
highlight_tags_map = get_tags_for_highlights_batch(conn, highlight_ids)

# Unfiltered item list — used to populate the "link to" dropdowns in each card
all_items_unfiltered = get_items(conn)

# Pre-load related items and links for every displayed item (avoids per-card queries)
related_map = {iid: get_tag_related_items(conn, iid, limit=4) for iid in item_ids}
links_map = {iid: get_item_links(conn, iid) for iid in item_ids}

conn.close()

# ─── Session state defaults ────────────────────────────────────────────────────

if "confirm_delete_item" not in st.session_state:
    st.session_state.confirm_delete_item = None
if "confirm_delete_highlight" not in st.session_state:
    st.session_state.confirm_delete_highlight = None


# ─── Card renderers ────────────────────────────────────────────────────────────
# Each function renders the full content of one expanded card.
# Widget keys are namespaced by item/highlight id to prevent collisions.


def _render_ai_section(entity_id: str, has_ai: bool, ai_summary: str, ai_insight: str):
    """
    Render the AI Insights block inside a card.
    Shows results if already processed; shows a 'Process' button otherwise.
    The button + spinner live here; the actual API call is in the caller
    because the caller needs to pass the right arguments.
    Returns True if the Process button was just clicked, False otherwise.
    """
    st.markdown("---")
    col_label, col_btn = st.columns([3, 1])

    with col_label:
        st.markdown("**AI Insights**")

    with col_btn:
        label = "Re-process" if has_ai else "Process with AI"
        clicked = st.button(label, key=f"process_{entity_id}", use_container_width=True)

    if has_ai:
        if ai_summary:
            st.markdown(f"**Summary:** {ai_summary}")
        if ai_insight:
            st.info(f"**Actionable insight:** {ai_insight}")
    else:
        st.caption("Not yet processed. Click 'Process with AI' to generate a summary, insight, and connections.")

    return clicked


def _render_suggestions(entity_id: str, suggestions: dict, is_item: bool):
    """
    If the just-processed suggestions are in session state, show them:
    suggested tags (with an Apply button) and related items.
    """
    if not suggestions:
        return

    tags = suggestions.get("tags", [])
    connections = suggestions.get("connections", [])

    if tags:
        st.markdown("**Suggested tags:** " + " ".join(f"`{t}`" for t in tags))
        if st.button("Add these tags", key=f"apply_tags_{entity_id}"):
            conn = get_conn()
            if is_item:
                apply_suggested_tags_to_item(conn, int(entity_id.split("_")[1]), tags)
            else:
                apply_suggested_tags_to_highlight(conn, int(entity_id.split("_")[1]), tags)
            conn.close()
            st.session_state.pop(f"suggestions_{entity_id}", None)
            st.rerun()

    if connections:
        st.markdown("**Related items:**")
        for c in connections:
            if c.get("title") and c.get("reason"):
                st.markdown(f"- **{c['title']}** — {c['reason']}")


def _render_rating_section(entity_id: str, current_rating: int, current_synthesis: str):
    """
    Render the 'Your Take' section: a 1-5 star rating + synthesis note.
    Writes to DB on save and shows a brief confirmation.
    """
    st.markdown("---")
    st.markdown("**Your take**")

    rating = st.select_slider(
        "Impact",
        options=[1, 2, 3, 4, 5],
        value=current_rating or 3,
        format_func=lambda x: "★" * x + "☆" * (5 - x),
        key=f"rating_{entity_id}",
    )

    synthesis = st.text_area(
        "My synthesis / what I'll do with this",
        value=current_synthesis or "",
        key=f"synthesis_{entity_id}",
        height=90,
        placeholder="How does this connect to your work? What will you actually do differently?",
    )

    if st.button("Save", key=f"save_rating_{entity_id}"):
        conn = get_conn()
        kind, raw_id = entity_id.split("_", 1)
        if kind == "item":
            update_item_rating(conn, int(raw_id), rating, synthesis or None)
        else:
            update_highlight_rating(conn, int(raw_id), rating, synthesis or None)
        conn.close()
        st.session_state[f"rating_saved_{entity_id}"] = True
        st.rerun()

    if st.session_state.pop(f"rating_saved_{entity_id}", False):
        st.success("Saved.")


def _render_related_section(item_id: int, related_items: list) -> None:
    """
    Show items that share tags with this one.
    Only rendered if there are any related items.
    """
    if not related_items:
        return

    st.markdown("---")
    st.markdown("**Related by tag**")
    for r in related_items:
        ct = r["content_type_name"] or "Unknown"
        n = r["shared_tags"]
        tag_word = "tag" if n == 1 else "tags"
        st.markdown(f"- **{r['title']}** &nbsp; `{ct}` &nbsp; *{n} shared {tag_word}*")


def _render_links_section(item_id: int, links: list, all_items_unfiltered: list) -> None:
    """
    Show existing manual links split into outgoing and incoming (backlinks),
    with remove buttons, plus a form to add new links.
    """
    st.markdown("---")
    st.markdown("**Links**")

    outgoing = [lnk for lnk in links if lnk["is_outgoing"]]
    incoming = [lnk for lnk in links if not lnk["is_outgoing"]]

    if outgoing:
        st.markdown("*Links to →*")
        for link in outgoing:
            label = link["relationship_label"] or "linked"
            txt_col, rm_col = st.columns([10, 1])
            with txt_col:
                st.markdown(f"→ **{link['other_title']}** &nbsp; _{label}_")
            with rm_col:
                if st.button("✕", key=f"rm_link_{link['id']}", help="Remove this link"):
                    conn = get_conn()
                    delete_item_link(conn, link["id"])
                    conn.close()
                    st.rerun()

    if incoming:
        if outgoing:
            st.markdown("")
        st.markdown("*Linked from ←*")
        for link in incoming:
            label = link["relationship_label"] or "linked"
            txt_col, rm_col = st.columns([10, 1])
            with txt_col:
                st.markdown(f"← **{link['other_title']}** &nbsp; _{label}_")
            with rm_col:
                if st.button("✕", key=f"rm_link_{link['id']}", help="Remove this link"):
                    conn = get_conn()
                    delete_item_link(conn, link["id"])
                    conn.close()
                    st.rerun()

    if not outgoing and not incoming:
        st.caption("No manual links yet.")

    # Add-link form (always visible, no nesting required)
    tgt_opts = {"— select item —": None}
    for i in all_items_unfiltered:
        if i["id"] != item_id:
            ct = i["content_type_name"] or "?"
            tgt_opts[f"{i['title']}  [{ct}]"] = i["id"]

    f1, f2, f3 = st.columns([4, 4, 1])
    with f1:
        selected_tgt = st.selectbox(
            "Target item",
            list(tgt_opts.keys()),
            key=f"lnk_tgt_{item_id}",
            label_visibility="collapsed",
        )
    with f2:
        rel_label = st.text_input(
            "Relationship label",
            key=f"lnk_rel_{item_id}",
            placeholder="expands on, contradicts, applies to, example of...",
            label_visibility="collapsed",
        )
    with f3:
        st.write("")
        st.write("")
        link_clicked = st.button("Link", key=f"lnk_btn_{item_id}", use_container_width=True)

    if link_clicked:
        target_id = tgt_opts.get(selected_tgt)
        if not target_id:
            st.error("Select a target item.")
        elif not rel_label.strip():
            st.error("Enter a relationship label.")
        else:
            conn = get_conn()
            add_item_link(conn, item_id, target_id, rel_label.strip())
            conn.close()
            for k in [f"lnk_tgt_{item_id}", f"lnk_rel_{item_id}"]:
                st.session_state.pop(k, None)
            st.rerun()


def render_item_card(item, tags: list, related_items: list = None, links: list = None, all_items_unfiltered: list = None):
    item_id = item["id"]
    entity_id = f"item_{item_id}"
    ct = item["content_type_name"] or "Unknown"
    date = format_date(item["created_at"])
    tag_str = "  ".join(f"`{t}`" for t in tags) if tags else "*no tags*"

    # Show impact rating in the header if it's been set
    stars = ("  ★" * item["impact_rating"]) if item["impact_rating"] else ""
    header = f"**{item['title']}** &nbsp;·&nbsp; `{ct}` &nbsp;·&nbsp; {date}{stars}"

    with st.expander(header):

        # ── Source and body ───────────────────────────────────────────
        if item["url"]:
            st.markdown(f"**Source:** [{item['url']}]({item['url']})")

        if item["body"]:
            st.markdown(item["body"])
        elif not item["ai_summary"]:
            st.caption("No notes added. Process with AI to generate a summary.")

        # ── Tags ──────────────────────────────────────────────────────
        st.markdown(f"**Tags:** {tag_str}")

        # ── Suggestions (from the most recent AI run this session) ────
        suggestions = st.session_state.get(f"suggestions_{entity_id}")
        _render_suggestions(entity_id, suggestions, is_item=True)

        # ── AI Insights ───────────────────────────────────────────────
        has_ai = bool(item["ai_summary"] or item["ai_insight"])
        process_clicked = _render_ai_section(
            entity_id,
            has_ai=has_ai,
            ai_summary=item["ai_summary"],
            ai_insight=item["ai_insight"],
        )

        if process_clicked:
            conn = get_conn()
            try:
                with st.spinner("Calling AI — this takes a few seconds..."):
                    context = get_library_for_ai_context(conn, exclude_id=item_id)
                    existing_tags = get_item_tags(conn, item_id)
                    result = process_item(
                        title=item["title"],
                        content_type=ct,
                        body=item["body"] or "",
                        url=item["url"] or "",
                        existing_tags=existing_tags,
                        library_items=context,
                    )
                    update_item_ai(conn, item_id, result["summary"], result["actionable_insight"])
                    st.session_state[f"suggestions_{entity_id}"] = {
                        "tags": result["suggested_tags"],
                        "connections": result["connections"],
                    }
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"AI error: {e}")
            finally:
                conn.close()
            st.rerun()

        # ── Your Take (rating + synthesis) ────────────────────────────
        _render_rating_section(
            entity_id,
            current_rating=item["impact_rating"],
            current_synthesis=item["synthesis_note"],
        )

        # ── Related items (by shared tag) ─────────────────────────────
        _render_related_section(item_id, related_items or [])

        # ── Manual links ──────────────────────────────────────────────
        _render_links_section(item_id, links or [], all_items_unfiltered or [])

        # ── Export + Delete ───────────────────────────────────────────
        st.markdown("---")
        exp_col, del_col = st.columns([1, 1])

        with exp_col:
            md_export = item_to_markdown(item, tags, links=links or [])
            fname = safe_filename(item["title"]) or f"item_{item_id}"
            st.download_button(
                "Export .md",
                data=md_export,
                file_name=f"{fname}.md",
                mime="text/markdown",
                key=f"export_{entity_id}",
            )

        with del_col:
            if st.button("Delete", key=f"del_{entity_id}", type="secondary"):
                st.session_state.confirm_delete_item = item_id
                st.rerun()

        if st.session_state.confirm_delete_item == item_id:
            st.warning(f"Delete \"{item['title']}\"? This cannot be undone.")
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete", key=f"yes_{entity_id}", type="primary"):
                conn = get_conn()
                delete_item(conn, item_id)
                conn.close()
                st.session_state.confirm_delete_item = None
                st.rerun()
            if c2.button("Cancel", key=f"no_{entity_id}"):
                st.session_state.confirm_delete_item = None
                st.rerun()


def render_highlight_card(h, tags: list):
    h_id = h["id"]
    entity_id = f"highlight_{h_id}"
    date = format_date(h["created_at"])
    tag_str = "  ".join(f"`{t}`" for t in tags) if tags else "*no tags*"

    preview = h["text"][:80] + ("..." if len(h["text"]) > 80 else "")
    source_part = f" — *{h['source_info']}*" if h["source_info"] else ""
    stars = ("  ★" * h["impact_rating"]) if h["impact_rating"] else ""
    header = f'"{preview}"{source_part} &nbsp;·&nbsp; {date}{stars}'

    with st.expander(header):

        # ── Full quote ────────────────────────────────────────────────
        st.markdown(f"> {h['text']}")

        meta = []
        if h["source_info"]:
            meta.append(h["source_info"])
        if h["parent_item_title"]:
            meta.append(f"from: **{h['parent_item_title']}**")
        if meta:
            st.caption(" &nbsp;·&nbsp; ".join(meta))

        # ── Tags ──────────────────────────────────────────────────────
        st.markdown(f"**Tags:** {tag_str}")

        # ── Suggestions ───────────────────────────────────────────────
        suggestions = st.session_state.get(f"suggestions_{entity_id}")
        _render_suggestions(entity_id, suggestions, is_item=False)

        # ── AI Insights ───────────────────────────────────────────────
        has_ai = bool(h["ai_summary"] or h["ai_insight"])
        process_clicked = _render_ai_section(
            entity_id,
            has_ai=has_ai,
            ai_summary=h["ai_summary"],
            ai_insight=h["ai_insight"],
        )

        if process_clicked:
            conn = get_conn()
            try:
                with st.spinner("Calling AI — this takes a few seconds..."):
                    context = get_library_for_ai_context(conn)
                    existing_tags = get_highlight_tags(conn, h_id)
                    result = process_highlight(
                        text=h["text"],
                        source_info=h["source_info"] or "",
                        parent_item_title=h["parent_item_title"] or "",
                        existing_tags=existing_tags,
                        library_items=context,
                    )
                    update_highlight_ai(conn, h_id, result["summary"], result["actionable_insight"])
                    st.session_state[f"suggestions_{entity_id}"] = {
                        "tags": result["suggested_tags"],
                        "connections": result["connections"],
                    }
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"AI error: {e}")
            finally:
                conn.close()
            st.rerun()

        # ── Your Take ─────────────────────────────────────────────────
        _render_rating_section(
            entity_id,
            current_rating=h["impact_rating"],
            current_synthesis=h["synthesis_note"],
        )

        # ── Delete ────────────────────────────────────────────────────
        st.markdown("---")
        if st.button("Delete", key=f"del_{entity_id}", type="secondary"):
            st.session_state.confirm_delete_highlight = h_id
            st.rerun()

        if st.session_state.confirm_delete_highlight == h_id:
            short = h["text"][:50] + "..."
            st.warning(f'Delete "{short}"? This cannot be undone.')
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete", key=f"yes_{entity_id}", type="primary"):
                conn = get_conn()
                delete_highlight(conn, h_id)
                conn.close()
                st.session_state.confirm_delete_highlight = None
                st.rerun()
            if c2.button("Cancel", key=f"no_{entity_id}"):
                st.session_state.confirm_delete_highlight = None
                st.rerun()


# ─── Tabs ─────────────────────────────────────────────────────────────────────

tab_items, tab_highlights = st.tabs([
    f"Items ({len(items)})",
    f"Highlights ({len(highlights)})",
])

with tab_items:
    if not items:
        if search or selected_ct_id or selected_tag:
            st.info("No items match your filters. Try broadening the search.")
        else:
            st.info("Your library is empty. Head to Capture to add your first item.")
    else:
        for item in items:
            render_item_card(
                item,
                item_tags_map.get(item["id"], []),
                related_items=related_map.get(item["id"], []),
                links=links_map.get(item["id"], []),
                all_items_unfiltered=all_items_unfiltered,
            )

with tab_highlights:
    if not highlights:
        if search or selected_tag:
            st.info("No highlights match your filters.")
        else:
            st.info("No highlights yet. Clip a quote from the Capture page.")
    else:
        for h in highlights:
            render_highlight_card(h, highlight_tags_map.get(h["id"], []))
