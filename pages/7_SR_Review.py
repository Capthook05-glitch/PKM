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

from styles import inject_css
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

inject_css()
init_db()

# ─── Color-coded rating button CSS ─────────────────────────────────────────────
# We wrap the 4 rating buttons in a container with id="sr-rating-row" and target
# each column's button by its nth-child position within that scoped container.

st.markdown("""
<style>
/* SR rating buttons — scoped to the rating row columns */

/* Again (col 1) = red */
div[data-testid="stHorizontalBlock"]:has(button[key*="sr_again"])
    > div:nth-child(1) button {
    background: rgba(231,76,60,0.15) !important;
    border: 1px solid rgba(231,76,60,0.55) !important;
    color: #e74c3c !important;
    font-weight: 600 !important;
}
div[data-testid="stHorizontalBlock"]:has(button[key*="sr_again"])
    > div:nth-child(1) button:hover {
    background: rgba(231,76,60,0.28) !important;
    border-color: #e74c3c !important;
}

/* Hard (col 2) = orange */
div[data-testid="stHorizontalBlock"]:has(button[key*="sr_again"])
    > div:nth-child(2) button {
    background: rgba(243,156,18,0.15) !important;
    border: 1px solid rgba(243,156,18,0.55) !important;
    color: #f39c12 !important;
    font-weight: 600 !important;
}
div[data-testid="stHorizontalBlock"]:has(button[key*="sr_again"])
    > div:nth-child(2) button:hover {
    background: rgba(243,156,18,0.28) !important;
    border-color: #f39c12 !important;
}

/* Good (col 3) = green */
div[data-testid="stHorizontalBlock"]:has(button[key*="sr_again"])
    > div:nth-child(3) button {
    background: rgba(46,204,113,0.18) !important;
    border: 1px solid rgba(46,204,113,0.55) !important;
    color: #2ecc71 !important;
    font-weight: 600 !important;
}
div[data-testid="stHorizontalBlock"]:has(button[key*="sr_again"])
    > div:nth-child(3) button:hover {
    background: rgba(46,204,113,0.30) !important;
    border-color: #2ecc71 !important;
}

/* Easy (col 4) = blue */
div[data-testid="stHorizontalBlock"]:has(button[key*="sr_again"])
    > div:nth-child(4) button {
    background: rgba(74,144,217,0.15) !important;
    border: 1px solid rgba(74,144,217,0.55) !important;
    color: #4a90d9 !important;
    font-weight: 600 !important;
}
div[data-testid="stHorizontalBlock"]:has(button[key*="sr_again"])
    > div:nth-child(4) button:hover {
    background: rgba(74,144,217,0.28) !important;
    border-color: #4a90d9 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #1e1f2e;">
    <h1 style="font-size:1.75rem;font-weight:700;color:#e8eaf0;margin:0 0 4px;">
        Spaced Repetition
    </h1>
    <p style="color:#525870;font-size:0.875rem;margin:0;">
        Review highlights at the right moment — before you forget them.
    </p>
</div>
""", unsafe_allow_html=True)

# ─── Stats row ─────────────────────────────────────────────────────────────────

conn = get_conn()
stats = get_sr_stats(conn)
conn.close()

c1, c2, c3 = st.columns(3)
STAT_ROWS = [
    (c1, "Due Today",             stats["due"],                                    "#e74c3c"),
    (c2, "Total in Queue",        stats["total"],                                  "#f39c12"),
    (c3, "Reviewed This Session", st.session_state.get("sr_session_count", 0),    "#2ecc71"),
]
for col, label, val, color in STAT_ROWS:
    col.markdown(f"""
<div style="background:#1a1b26;border:1px solid #2a2b3d;border-top:3px solid {color};
            border-radius:10px;padding:16px 20px;box-shadow:0 2px 12px rgba(0,0,0,0.3);">
    <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;
                letter-spacing:0.09em;color:#525870;margin-bottom:4px;">{label}</div>
    <div style="font-size:2rem;font-weight:700;color:#e8eaf0;">{val}</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

if stats["due"] == 0:
    st.success(
        "Nothing due right now — you're all caught up! "
        "Come back later or add more highlights from the Capture page."
    )
    st.stop()

# ─── Session queue ──────────────────────────────────────────────────────────────

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

# ─── Progress bar ──────────────────────────────────────────────────────────────

total_session = st.session_state.get("sr_session_total", len(queue))
if "sr_session_total" not in st.session_state:
    st.session_state["sr_session_total"] = len(queue)

done = st.session_state["sr_session_total"] - len(queue)
pct = done / st.session_state["sr_session_total"] if st.session_state["sr_session_total"] else 0

st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
    <span style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.07em;color:#525870;">Session Progress</span>
    <span style="font-size:0.78rem;color:#4a90d9;font-weight:600;">
        {done} / {st.session_state['sr_session_total']}
    </span>
</div>
""", unsafe_allow_html=True)
st.progress(pct)

# ─── Current card ──────────────────────────────────────────────────────────────

card = queue[0]
h_id = card["id"]

conn = get_conn()
tags = get_highlight_tags(conn, h_id)
conn.close()

# Flashcard display
meta_parts = []
if card.get("source_info"):
    meta_parts.append(card["source_info"])
if card.get("parent_item_title"):
    meta_parts.append(f"from {card['parent_item_title']}")
meta_html = (
    f'<div style="font-size:0.82rem;color:#525870;margin-top:14px;letter-spacing:0.01em;">'
    f'— {" · ".join(meta_parts)}</div>'
) if meta_parts else ""

with st.container(border=True):
    st.markdown(f"""
<div style="text-align:center;padding:32px 24px 24px;max-width:680px;margin:0 auto;">
    <div style="
        font-size:1.3rem;
        font-family:'Lora',Georgia,serif;
        font-style:italic;
        color:#e8eaf0;
        line-height:1.72;
        position:relative;
    ">
        <span style="
            font-size:4rem;color:#2a2b3d;
            position:absolute;top:-18px;left:-4px;
            line-height:1;font-style:normal;font-family:serif;
        ">\u201c</span>
        <span style="position:relative;z-index:1;">{card['text']}</span>
        <span style="
            font-size:4rem;color:#2a2b3d;
            line-height:1;font-style:normal;font-family:serif;
            vertical-align:bottom;
        ">\u201d</span>
    </div>
    {meta_html}
</div>
""", unsafe_allow_html=True)

    # Context toggle
    show_ctx = st.toggle("Show context", key=f"ctx_{h_id}")

    if show_ctx:
        st.markdown('<div style="border-top:1px solid #1e1f2e;padding-top:14px;margin-top:4px;">', unsafe_allow_html=True)
        if tags:
            pill_html = "".join(
                f'<span style="background:rgba(74,144,217,0.12);color:#7eb8f7;'
                f'border-radius:4px;padding:2px 8px;font-size:0.78rem;margin-right:4px;">{t}</span>'
                for t in tags
            )
            st.markdown(f'<div style="margin-bottom:10px;">{pill_html}</div>', unsafe_allow_html=True)
        if card.get("ai_summary"):
            st.markdown(f"**AI summary:** {card['ai_summary']}")
        if card.get("ai_insight"):
            st.info(f"**Insight:** {card['ai_insight']}")
        if card.get("synthesis_note"):
            st.markdown(f"**Your synthesis:** {card['synthesis_note']}")

        interval = card.get("sr_interval") or 1
        reps = card.get("sr_repetitions") or 0
        st.caption(f"Repetitions: {reps}  ·  Current interval: {interval} day(s)")
        st.markdown('</div>', unsafe_allow_html=True)

# ─── Rating buttons ─────────────────────────────────────────────────────────────

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

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
        type="secondary",
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

    st.session_state["sr_queue"].pop(0)
    st.session_state["sr_session_count"] = st.session_state.get("sr_session_count", 0) + 1
    st.rerun()

# ─── Skip ──────────────────────────────────────────────────────────────────────

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
if st.button("Skip (come back to this one)", key=f"sr_skip_{h_id}"):
    card = st.session_state["sr_queue"].pop(0)
    st.session_state["sr_queue"].append(card)
    st.rerun()
