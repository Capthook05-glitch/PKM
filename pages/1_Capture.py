"""
pages/1_Capture.py — Add new content to your knowledge base.

Two tabs:
  Item     — anything you've read, watched, listened to, or written.
             URL field has a "Fetch title" button that auto-fills the title.
  Highlight — a quote or passage, optionally linked to an existing item.

Both tabs let you tag freely (comma-separated).
Content types are user-customizable: an inline expander lets you add new
types without leaving the form.
"""

import streamlit as st
from database import (
    init_db,
    get_conn,
    add_content_type,
    add_item,
    add_highlight,
    get_content_types,
    get_items,
    get_all_tags,
)
from utils import fetch_page_title, parse_tags, parse_kindle_clippings

st.set_page_config(page_title="Capture", layout="wide")

init_db()

st.title("Capture")
st.caption("Add something to your knowledge base.")

tab_item, tab_highlight, tab_import = st.tabs(["Item", "Highlight", "Import"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _show_tag_hint(all_tags: list) -> str:
    """Build the help string shown below the tags input."""
    if not all_tags:
        return "No tags in library yet — type any you like."
    sample = ", ".join(all_tags[:12])
    suffix = "..." if len(all_tags) > 12 else ""
    return f"Existing tags: {sample}{suffix}"


# ─── Item tab ─────────────────────────────────────────────────────────────────

with tab_item:

    # Load data needed to render the form
    conn = get_conn()
    content_types = get_content_types(conn)
    all_tags = get_all_tags(conn)
    conn.close()

    ct_names = [ct["name"] for ct in content_types]
    ct_id_by_name = {ct["name"]: ct["id"] for ct in content_types}

    # ── Success banner (set by the save handler on the previous run) ──
    if st.session_state.get("item_saved_msg"):
        st.success(st.session_state.pop("item_saved_msg"))

    # ── URL + auto-fetch ───────────────────────────────────────────────
    st.subheader("Source")
    url_col, btn_col = st.columns([5, 1])

    with url_col:
        url_input = st.text_input(
            "URL (optional)",
            key="item_url",
            placeholder="https://...",
        )
    with btn_col:
        st.write("")
        st.write("")
        fetch_clicked = st.button("Fetch title", key="fetch_title_btn", use_container_width=True)

    # When the button is clicked, try to pull the page title and store it
    # in session state so the title widget below picks it up.
    if fetch_clicked:
        if url_input:
            with st.spinner("Fetching page title..."):
                fetched = fetch_page_title(url_input)
            if fetched:
                st.session_state["item_title"] = fetched
                st.session_state["fetch_status"] = "ok"
                st.rerun()
            else:
                st.session_state["fetch_status"] = "fail"
        else:
            st.warning("Paste a URL first, then click Fetch title.")

    if st.session_state.get("fetch_status") == "fail":
        st.warning("Could not fetch the title automatically — enter it below.")
    if st.session_state.get("fetch_status") == "ok":
        st.success("Title fetched. Edit it if needed.")

    # ── Core fields ───────────────────────────────────────────────────
    st.subheader("Details")

    title_input = st.text_input(
        "Title *",
        key="item_title",
        placeholder="What is this?",
    )

    # Content type selector + inline "add new type" expander side by side
    ct_col, new_ct_col = st.columns([3, 2])

    with ct_col:
        selected_ct = st.selectbox(
            "Content type *",
            options=ct_names,
            key="item_ct",
        )

    with new_ct_col:
        with st.expander("Add a new content type"):
            new_ct_name = st.text_input(
                "Type name",
                key="new_ct_input",
                placeholder='e.g. "Course", "Conference Talk"',
            )
            if st.button("Add type", key="add_ct_btn"):
                if new_ct_name.strip():
                    conn = get_conn()
                    add_content_type(conn, new_ct_name.strip())
                    conn.close()
                    st.success(f'Added "{new_ct_name.strip()}"')
                    st.rerun()
                else:
                    st.error("Enter a name first.")

    body_input = st.text_area(
        "Notes / body (optional)",
        key="item_body",
        placeholder=(
            "Your thoughts, a description, a summary, or paste the full text. "
            "This is also where a Fleeting Note lives — just type your idea here."
        ),
        height=160,
    )

    tags_input = st.text_input(
        "Tags (comma-separated)",
        key="item_tags",
        placeholder="anxiety, cbt, motivation",
        help=_show_tag_hint(all_tags),
    )

    # ── Save ──────────────────────────────────────────────────────────
    if st.button("Save Item", type="primary", key="save_item_btn"):
        current_title = st.session_state.get("item_title", "").strip()
        if not current_title:
            st.error("Title is required.")
        elif selected_ct not in ct_id_by_name:
            st.error("Select a valid content type.")
        else:
            tag_list = parse_tags(st.session_state.get("item_tags", ""))
            conn = get_conn()
            item_id = add_item(
                conn,
                title=current_title,
                content_type_id=ct_id_by_name[selected_ct],
                url=st.session_state.get("item_url") or None,
                body=st.session_state.get("item_body") or None,
                tag_names=tag_list,
            )
            conn.close()

            # Clear the form by removing its session state keys, then rerun
            for key in ["item_title", "item_url", "item_body", "item_tags", "fetch_status"]:
                st.session_state.pop(key, None)
            st.session_state["item_saved_msg"] = (
                f"Saved \"{current_title}\" (#{item_id})"
            )
            st.rerun()


# ─── Highlight tab ────────────────────────────────────────────────────────────

with tab_highlight:

    conn = get_conn()
    all_items = get_items(conn)
    all_tags = get_all_tags(conn)
    conn.close()

    # ── Success banner ────────────────────────────────────────────────
    if st.session_state.get("highlight_saved_msg"):
        st.success(st.session_state.pop("highlight_saved_msg"))

    st.subheader("The quote or passage")

    highlight_text = st.text_area(
        "Highlight *",
        key="highlight_text",
        placeholder="Paste the exact quote or passage here...",
        height=160,
    )

    source_info = st.text_input(
        "Source (optional)",
        key="highlight_source",
        placeholder='"Thinking, Fast and Slow, p. 47" or "Tim Ferriss podcast, ep. 612"',
    )

    # Optional parent item link — build a lookup dict keyed by display label
    item_options = {"(None — standalone highlight)": None}
    for item in all_items:
        ct = item["content_type_name"] or "Unknown"
        label = f"{item['title']}  [{ct}]"
        item_options[label] = item["id"]

    selected_item_label = st.selectbox(
        "Link to an item (optional)",
        options=list(item_options.keys()),
        key="highlight_parent",
        help="Tie this highlight to a source item you've already added.",
    )
    parent_item_id = item_options[selected_item_label]

    tags_input_h = st.text_input(
        "Tags (comma-separated)",
        key="highlight_tags",
        placeholder="anxiety, insight, reframe",
        help=_show_tag_hint(all_tags),
    )

    # ── Save ──────────────────────────────────────────────────────────
    if st.button("Save Highlight", type="primary", key="save_highlight_btn"):
        current_text = st.session_state.get("highlight_text", "").strip()
        if not current_text:
            st.error("Highlight text is required.")
        else:
            tag_list = parse_tags(st.session_state.get("highlight_tags", ""))
            conn = get_conn()
            h_id = add_highlight(
                conn,
                text=current_text,
                source_info=st.session_state.get("highlight_source") or None,
                parent_item_id=parent_item_id,
                tag_names=tag_list,
            )
            conn.close()

            # Clear the form
            for key in ["highlight_text", "highlight_source", "highlight_tags"]:
                st.session_state.pop(key, None)
            preview = current_text[:60] + ("..." if len(current_text) > 60 else "")
            st.session_state["highlight_saved_msg"] = f'Saved highlight #{h_id}: "{preview}"'
            st.rerun()


# ─── Import tab ───────────────────────────────────────────────────────────────

with tab_import:

    st.subheader("Import from Kindle")
    st.caption(
        "On your Kindle, plug it in to your computer and open the `documents` folder. "
        "Upload the **My Clippings.txt** file here to bulk-import your highlights."
    )

    uploaded = st.file_uploader("My Clippings.txt", type=["txt"], key="kindle_upload")

    if uploaded:
        raw = uploaded.read().decode("utf-8", errors="replace")
        parsed = parse_kindle_clippings(raw)

        if not parsed:
            st.warning("No highlights found in this file. Make sure it's a valid My Clippings.txt.")
        else:
            st.success(f"Found **{len(parsed)} highlights** across your Kindle library.")

            # Show preview
            with st.expander(f"Preview all {len(parsed)} highlights"):
                for i, h in enumerate(parsed[:50]):
                    st.markdown(f"**{i+1}. {h['title']}**" + (f" — {h['author']}" if h["author"] else ""))
                    st.markdown(f"> {h['text'][:200]}" + ("..." if len(h["text"]) > 200 else ""))
                    st.caption(h["source_info"])
                    st.markdown("---")
                if len(parsed) > 50:
                    st.caption(f"... and {len(parsed) - 50} more.")

            # Dedup against existing highlights in DB
            conn = get_conn()
            existing_texts = {
                row["text"].strip()
                for row in conn.execute("SELECT text FROM highlights").fetchall()
            }
            conn.close()

            new_highlights = [h for h in parsed if h["text"].strip() not in existing_texts]
            dupes = len(parsed) - len(new_highlights)

            if dupes:
                st.info(f"{dupes} highlight(s) already in your library will be skipped.")

            if not new_highlights:
                st.success("All highlights are already in your library — nothing to import.")
            else:
                st.markdown(f"**{len(new_highlights)} new highlights** ready to import.")
                tags_for_import = st.text_input(
                    "Tags to apply to all imported highlights (comma-separated, optional)",
                    key="kindle_tags",
                    placeholder="kindle, reading, book",
                )
                if st.button("Import All", type="primary", key="kindle_import_btn"):
                    tag_list = parse_tags(tags_for_import)
                    conn = get_conn()
                    for h in new_highlights:
                        add_highlight(
                            conn,
                            text=h["text"],
                            source_info=h["source_info"] or None,
                            parent_item_id=None,
                            tag_names=tag_list,
                        )
                    conn.close()
                    st.session_state["kindle_imported"] = len(new_highlights)
                    st.rerun()

    if st.session_state.get("kindle_imported"):
        n = st.session_state.pop("kindle_imported")
        st.success(f"Imported {n} highlights. Head to the Library to browse them.")

    st.markdown("---")
    st.subheader("Paste highlights (any format)")
    st.caption(
        "Paste highlights line by line — one highlight per paragraph — to bulk-add them quickly. "
        "Each non-empty paragraph becomes one highlight."
    )

    bulk_text = st.text_area(
        "Paste highlights here",
        key="bulk_paste",
        height=200,
        placeholder="Paste your highlights here, separated by blank lines...",
    )
    bulk_source = st.text_input(
        "Source (optional — applies to all)",
        key="bulk_source",
        placeholder="Thinking, Fast and Slow — Daniel Kahneman",
    )
    bulk_tags = st.text_input(
        "Tags (comma-separated, optional)",
        key="bulk_tags",
        placeholder="book, psychology",
    )

    if st.button("Import pasted highlights", type="primary", key="bulk_import_btn"):
        paragraphs = [p.strip() for p in bulk_text.split("\n\n") if p.strip()]
        if not paragraphs:
            st.error("Paste at least one highlight.")
        else:
            tag_list = parse_tags(bulk_tags)
            conn = get_conn()
            for para in paragraphs:
                add_highlight(
                    conn,
                    text=para,
                    source_info=bulk_source.strip() or None,
                    parent_item_id=None,
                    tag_names=tag_list,
                )
            conn.close()
            st.success(f"Imported {len(paragraphs)} highlight(s).")
            for k in ["bulk_paste", "bulk_source", "bulk_tags"]:
                st.session_state.pop(k, None)
            st.rerun()
