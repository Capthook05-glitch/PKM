"""
pages/7_SR_Review.py — Spaced-repetition flashcard review (Readwise style).

Highlights are scheduled using the SM-2 algorithm:
  - New highlights surface immediately.
  - After each review you press one of four buttons:
      Again  → forgot it; resets to 1-day interval
      Hard   → remembered with effort; mild interval growth
      Good   → solid recall; normal interval growth
      Easy   → instant recall; fast interval growth + ease bump
  - The next due date is stored on the highlight so reviews spread out
    over days, weeks, and months naturally.

The card shows the highlight text. Clicking "Show context" reveals:
  source, parent item, tags, AI summary/insight, and your synthesis note.
"""

import streamlit as st

from database import (
    get_conn,
    get_highlight_tags,
    get_sr_due_highlights,
    get_sr_stats,
    init_db,
    update_sr_schedule,
)
from utils import format_date

st.set_page_config(page_title="SR Review", layout="wide")

init_db()

st.title("Spaced Repetition")
st.caption("Review highlights at the right moment — before you forget them.")

# ─── Stats row ─────────────────────────────────────────────────────────────────

conn = get_conn()
stats = get_sr_stats(conn)
conn.close()

c1, c2, c3 = st.columns(3)
c1.metric("Due today", stats["due"])
c2.metric("Total in queue", stats["total"])
c3.metric("Reviewed this session", st.session_state.get("sr_session_count", 0))

st.markdown("---")

if stats["due"] == 0:
    st.success(
        "Nothing due right now — you're all caught up! "
        "Come back later or add more highlights from the Capture page."
    )
    st.stop()

# ─── Session queue ──────────────────────────────────────────────────────────────
# Load the queue once per session (fixed until the user resets or finishes).

if "sr_queue" not in st.session_state or not st.session_state["sr_queue"]:
    conn = get_conn()
    due = get_sr_due_highlights(conn, limit=50)
    conn.close()
    st.session_state["sr_queue"] = [dict(h) for h in due]
    st.session_state["sr_session_count"] = 0

queue = st.session_state["sr_queue"]

if not queue:
    st.success("All done for this session! Great work.")
    if st.button("Start a new session"):
        st.session_state.pop("sr_queue", None)
        st.session_state["sr_session_count"] = 0
        st.rerun()
    st.stop()

# Progress bar
total_session = st.session_state.get("sr_session_total", len(queue))
if "sr_session_total" not in st.session_state:
    st.session_state["sr_session_total"] = len(queue)

done = st.session_state["sr_session_total"] - len(queue)
st.progress(done / st.session_state["sr_session_total"])
st.caption(f"{done} of {st.session_state['sr_session_total']} reviewed this session")

# ─── Current card ──────────────────────────────────────────────────────────────

card = queue[0]
h_id = card["id"]

conn = get_conn()
tags = get_highlight_tags(conn, h_id)
conn.close()

# Card display
with st.container(border=True):
    st.markdown(f"### \"{card['text']}\"")

    meta_parts = []
    if card.get("source_info"):
        meta_parts.append(card["source_info"])
    if card.get("parent_item_title"):
        meta_parts.append(f"from: *{card['parent_item_title']}*")
    if meta_parts:
        st.caption("  ·  ".join(meta_parts))

    # Context toggle
    show_ctx = st.toggle("Show context", key=f"ctx_{h_id}")

    if show_ctx:
        st.markdown("---")
        if tags:
            st.markdown("**Tags:** " + "  ".join(f"`{t}`" for t in tags))
        if card.get("ai_summary"):
            st.markdown(f"**AI summary:** {card['ai_summary']}")
        if card.get("ai_insight"):
            st.info(f"**Insight:** {card['ai_insight']}")
        if card.get("synthesis_note"):
            st.markdown(f"**Your synthesis:** {card['synthesis_note']}")

        # SR metadata
        interval = card.get("sr_interval") or 1
        reps = card.get("sr_repetitions") or 0
        st.caption(f"Repetitions: {reps}  ·  Current interval: {interval} day(s)")

# ─── Rating buttons ─────────────────────────────────────────────────────────────

st.markdown("")

col_a, col_h, col_g, col_e = st.columns(4)

rating_clicked = None

with col_a:
    if st.button(
        "Again",
        key=f"sr_again_{h_id}",
        use_container_width=True,
        help="Forgot it — review again tomorrow",
        type="secondary",
    ):
        rating_clicked = 0

with col_h:
    if st.button(
        "Hard",
        key=f"sr_hard_{h_id}",
        use_container_width=True,
        help="Remembered with serious effort",
        type="secondary",
    ):
        rating_clicked = 1

with col_g:
    if st.button(
        "Good",
        key=f"sr_good_{h_id}",
        use_container_width=True,
        help="Correct after a moment",
        type="primary",
    ):
        rating_clicked = 2

with col_e:
    if st.button(
        "Easy",
        key=f"sr_easy_{h_id}",
        use_container_width=True,
        help="Instant recall — push it further out",
        type="secondary",
    ):
        rating_clicked = 3

if rating_clicked is not None:
    conn = get_conn()
    update_sr_schedule(conn, h_id, rating_clicked)
    conn.close()

    # Advance the queue
    st.session_state["sr_queue"].pop(0)
    st.session_state["sr_session_count"] = st.session_state.get("sr_session_count", 0) + 1
    st.rerun()

# ─── Skip ──────────────────────────────────────────────────────────────────────

st.markdown("")
if st.button("Skip (come back to this one)", key=f"sr_skip_{h_id}"):
    # Move current card to the end of the queue
    card = st.session_state["sr_queue"].pop(0)
    st.session_state["sr_queue"].append(card)
    st.rerun()
