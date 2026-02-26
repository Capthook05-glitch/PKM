"""
app.py — Home page / entry point for the PKM app.

This file does three things:
  1. Calls init_db() so the database and tables are created on first launch.
  2. Shows a quick-glance dashboard: library stats + recent captures.
  3. Provides navigation links to the Capture and Library pages.
"""

import streamlit as st
from database import init_db, get_conn, get_stats, get_items, get_highlights
from utils import format_date

st.set_page_config(
    page_title="PKM — Knowledge Base",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Run once per cold start. Safe to call every render — uses IF NOT EXISTS.
init_db()

# ─── Header ───────────────────────────────────────────────────────────────────

st.title("Personal Knowledge Base")
st.caption("Capture fast. Surface insights. Connect ideas.")

st.markdown("---")

# ─── Stats row ────────────────────────────────────────────────────────────────

conn = get_conn()
stats = get_stats(conn)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Items", stats["items"], help="Articles, books, podcasts, videos, notes")
col2.metric("Highlights", stats["highlights"], help="Quotes and passages you've clipped")
col3.metric("Tags", stats["tags"], help="Unique tags across your whole library")
col4.metric("Links", stats["links"], help="Manual connections between items (Phase 3)")

st.markdown("---")

# ─── Recent captures ──────────────────────────────────────────────────────────

st.subheader("Recently captured")

recent_items = get_items(conn, limit=5)
recent_highlights = get_highlights(conn, limit=5)
conn.close()

left, right = st.columns(2)

with left:
    st.markdown("**Items**")
    if not recent_items:
        st.info("No items yet. Use Capture to add your first one.")
    else:
        for item in recent_items:
            ct = item["content_type_name"] or "Unknown"
            date = format_date(item["created_at"])
            st.markdown(f"- **{item['title']}** &nbsp; `{ct}` &nbsp; *{date}*")

with right:
    st.markdown("**Highlights**")
    if not recent_highlights:
        st.info("No highlights yet. Clip a quote from something you've read.")
    else:
        for h in recent_highlights:
            preview = h["text"][:90] + ("..." if len(h["text"]) > 90 else "")
            date = format_date(h["created_at"])
            source = f" — *{h['source_info']}*" if h["source_info"] else ""
            st.markdown(f'- "{preview}"{source} &nbsp; *{date}*')

st.markdown("---")

# ─── Quick navigation ─────────────────────────────────────────────────────────

st.subheader("Where do you want to go?")

nav1, nav2 = st.columns(2)

with nav1:
    st.page_link("pages/1_Capture.py", label="Capture something new", icon="📥")
    st.caption("Add an item, paste a highlight, or drop a fleeting thought.")

with nav2:
    st.page_link("pages/2_Library.py", label="Browse your library", icon="📚")
    st.caption("Search, filter by type or tag, and read what you've saved.")
