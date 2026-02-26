"""
pages/3_Review.py — Daily review and forgotten gems.

Two sections:

  Today's Mix      — 5 random items/highlights from your library (at least 7 days
                     old so you're always looking back, not just at what you
                     captured today). The selection is fixed for the session —
                     interacting with one card won't reshuffle the others.
                     Hit Shuffle for a fresh set.

  Forgotten Gems   — Items you captured 30+ days ago that you've never rated
                     or added a synthesis note to. These are sitting in your
                     library without any engagement. The oldest appear first.

Each card lets you:
  - Read the AI summary + insight (if processed), or the raw content
  - Rate impact (1-5 stars) and add a synthesis note
  - Run AI processing inline if the item hasn't been processed yet
"""

import streamlit as st
from datetime import date

from ai import process_item, process_highlight
from database import (
    init_db,
    get_conn,
    get_daily_review_items,
    get_daily_review_highlights,
    get_forgotten_items,
    get_item_tags,
    get_highlight_tags,
    get_tags_for_items_batch,
    get_tags_for_highlights_batch,
    get_library_for_ai_context,
    update_item_ai,
    update_highlight_ai,
    update_item_rating,
    update_highlight_rating,
)
from utils import format_date

st.set_page_config(page_title="Daily Review", layout="wide")

init_db()

st.title("Daily Review")
st.caption(date.today().strftime("%A, %B %-d, %Y"))

# ─── Session-stable daily selection ───────────────────────────────────────────
# We store only the IDs in session state. The actual data is re-read from the
# DB on every render so ratings/summaries always show their latest values.

def _load_daily_mix() -> None:
    """Pick today's random items and store their IDs in session state."""
    conn = get_conn()
    rv_items = get_daily_review_items(conn, n=3, min_age_days=7)
    rv_highlights = get_daily_review_highlights(conn, n=2, min_age_days=7)
    conn.close()
    st.session_state["rev_item_ids"] = [i["id"] for i in rv_items]
    st.session_state["rev_highlight_ids"] = [h["id"] for h in rv_highlights]


if "rev_item_ids" not in st.session_state:
    _load_daily_mix()

_, shuffle_col = st.columns([7, 1])
with shuffle_col:
    if st.button("Shuffle", key="shuffle_btn", use_container_width=True):
        _load_daily_mix()
        st.rerun()

# ─── Load data for the stored IDs ─────────────────────────────────────────────

rev_item_ids = st.session_state["rev_item_ids"]
rev_highlight_ids = st.session_state["rev_highlight_ids"]

conn = get_conn()

review_items = []
for iid in rev_item_ids:
    row = conn.execute(
        """
        SELECT i.*, ct.name AS content_type_name
        FROM items i
        LEFT JOIN content_types ct ON ct.id = i.content_type_id
        WHERE i.id = ?
        """,
        (iid,),
    ).fetchone()
    if row:
        review_items.append(row)

review_highlights = []
for hid in rev_highlight_ids:
    row = conn.execute(
        """
        SELECT h.*, i.title AS parent_item_title
        FROM highlights h
        LEFT JOIN items i ON i.id = h.parent_item_id
        WHERE h.id = ?
        """,
        (hid,),
    ).fetchone()
    if row:
        review_highlights.append(row)

item_tags_map = get_tags_for_items_batch(conn, [i["id"] for i in review_items])
highlight_tags_map = get_tags_for_highlights_batch(conn, [h["id"] for h in review_highlights])

forgotten = get_forgotten_items(conn, days=30, limit=6)
forgotten_tags_map = get_tags_for_items_batch(conn, [f["id"] for f in forgotten])

conn.close()


# ─── Card renderers ────────────────────────────────────────────────────────────

def _render_card_content_item(item, tags: list) -> None:
    """The top portion of an item review card (content, not actions)."""
    ct = item["content_type_name"] or "Unknown"
    st.caption(f"`{ct}` · {format_date(item['created_at'])}")
    st.markdown(f"#### {item['title']}")

    has_ai = bool(item["ai_summary"] or item["ai_insight"])

    if has_ai:
        if item["ai_summary"]:
            st.markdown(f"**Summary:** {item['ai_summary']}")
        if item["ai_insight"]:
            st.info(f"**Insight:** {item['ai_insight']}")
    elif item["body"]:
        preview = item["body"][:300] + ("..." if len(item["body"]) > 300 else "")
        st.markdown(preview)
    else:
        st.caption("No content or summary yet.")

    if item["url"]:
        st.caption(f"[Source URL]({item['url']})")

    if tags:
        st.markdown("**Tags:** " + " ".join(f"`{t}`" for t in tags))


def _render_card_content_highlight(h, tags: list) -> None:
    """The top portion of a highlight review card."""
    meta_parts = []
    if h["source_info"]:
        meta_parts.append(h["source_info"])
    if h["parent_item_title"]:
        meta_parts.append(f"from: {h['parent_item_title']}")

    meta_str = " · ".join(meta_parts) if meta_parts else ""
    st.caption(f"Highlight · {format_date(h['created_at'])}" + (f" · {meta_str}" if meta_str else ""))

    st.markdown(f"> {h['text']}")

    has_ai = bool(h["ai_summary"] or h["ai_insight"])
    if has_ai:
        if h["ai_summary"]:
            st.markdown(f"**Summary:** {h['ai_summary']}")
        if h["ai_insight"]:
            st.info(f"**Insight:** {h['ai_insight']}")

    if tags:
        st.markdown("**Tags:** " + " ".join(f"`{t}`" for t in tags))


def _render_rating_and_actions(entity_id: str, current_rating, current_synthesis, row, is_item: bool) -> None:
    """
    Rating slider + synthesis input + Save.
    Also shows 'Process with AI' if the item hasn't been processed yet.

    entity_id format:  "item_42"  or  "highlight_7"
    """
    st.markdown("---")

    has_ai = bool(row["ai_summary"] or row["ai_insight"])

    # Rating + synthesis row
    r_col, s_col, btn_col = st.columns([3, 5, 1])

    with r_col:
        rating = st.select_slider(
            "Impact",
            options=[1, 2, 3, 4, 5],
            value=current_rating or 3,
            format_func=lambda x: "★" * x + "☆" * (5 - x),
            key=f"rev_rating_{entity_id}",
        )

    with s_col:
        synthesis = st.text_input(
            "Synthesis",
            value=current_synthesis or "",
            key=f"rev_syn_{entity_id}",
            placeholder="What will you do with this?",
            label_visibility="collapsed",
        )

    with btn_col:
        st.write("")
        st.write("")
        if st.button("Save", key=f"rev_save_{entity_id}", use_container_width=True):
            conn = get_conn()
            raw_id = int(entity_id.split("_", 1)[1])
            if is_item:
                update_item_rating(conn, raw_id, rating, synthesis or None)
            else:
                update_highlight_rating(conn, raw_id, rating, synthesis or None)
            conn.close()
            st.session_state[f"rev_saved_{entity_id}"] = True
            st.rerun()

    if st.session_state.pop(f"rev_saved_{entity_id}", False):
        st.success("Saved.")

    # AI processing button (only shown if not yet processed)
    if not has_ai:
        if st.button(
            "Process with AI",
            key=f"rev_proc_{entity_id}",
            help="Generate a summary, actionable insight, and suggested tags.",
        ):
            raw_id = int(entity_id.split("_", 1)[1])
            conn = get_conn()
            try:
                with st.spinner("Calling AI — a few seconds..."):
                    if is_item:
                        context = get_library_for_ai_context(conn, exclude_id=raw_id)
                        existing_tags = get_item_tags(conn, raw_id)
                        result = process_item(
                            title=row["title"],
                            content_type=row["content_type_name"] or "Unknown",
                            body=row["body"] or "",
                            url=row["url"] or "",
                            existing_tags=existing_tags,
                            library_items=context,
                        )
                        update_item_ai(conn, raw_id, result["summary"], result["actionable_insight"])
                    else:
                        context = get_library_for_ai_context(conn)
                        existing_tags = get_highlight_tags(conn, raw_id)
                        result = process_highlight(
                            text=row["text"],
                            source_info=row["source_info"] or "",
                            parent_item_title=row["parent_item_title"] or "",
                            existing_tags=existing_tags,
                            library_items=context,
                        )
                        update_highlight_ai(conn, raw_id, result["summary"], result["actionable_insight"])
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"AI error: {e}")
            finally:
                conn.close()
            st.rerun()


def render_review_item(item, tags: list) -> None:
    entity_id = f"item_{item['id']}"
    with st.container(border=True):
        _render_card_content_item(item, tags)
        _render_rating_and_actions(
            entity_id,
            current_rating=item["impact_rating"],
            current_synthesis=item["synthesis_note"],
            row=item,
            is_item=True,
        )


def render_review_highlight(h, tags: list) -> None:
    entity_id = f"highlight_{h['id']}"
    with st.container(border=True):
        _render_card_content_highlight(h, tags)
        _render_rating_and_actions(
            entity_id,
            current_rating=h["impact_rating"],
            current_synthesis=h["synthesis_note"],
            row=h,
            is_item=False,
        )


# ─── Today's Mix ──────────────────────────────────────────────────────────────

total = len(review_items) + len(review_highlights)
st.subheader(f"Today's mix ({total})")
st.caption("Older items from your library, randomly selected. Rate them, add your synthesis, or run AI processing.")

if total == 0:
    st.info(
        "Your library doesn't have enough items yet, or nothing is old enough to review. "
        "Capture more content, then come back."
    )
else:
    # Interleave: item, highlight, item, highlight, item
    combined = []
    item_iter = iter(review_items)
    hl_iter = iter(review_highlights)
    for item in item_iter:
        combined.append(("item", item))
        hl = next(hl_iter, None)
        if hl:
            combined.append(("highlight", hl))
    for hl in hl_iter:
        combined.append(("highlight", hl))

    for kind, row in combined:
        if kind == "item":
            render_review_item(row, item_tags_map.get(row["id"], []))
        else:
            render_review_highlight(row, highlight_tags_map.get(row["id"], []))

# ─── Forgotten Gems ───────────────────────────────────────────────────────────

st.markdown("---")
st.subheader(f"Forgotten gems ({len(forgotten)})")
st.caption(
    "Items you captured 30+ days ago with no rating and no synthesis note. "
    "Oldest first — what slipped through the cracks?"
)

if not forgotten:
    st.info(
        "No forgotten gems right now. Either your library is new (nothing is 30+ days old yet), "
        "or you've engaged with everything — nice work."
    )
else:
    for item in forgotten:
        render_review_item(item, forgotten_tags_map.get(item["id"], []))
