"""
app.py — Home page / entry point for the PKM app.

This file does three things:
  1. Calls init_db() so the database and tables are created on first launch.
  2. Shows a quick-glance dashboard: library stats + recent captures.
  3. Provides navigation links to the Capture and Library pages.
"""

import streamlit as st
from database import init_db, get_conn, get_stats, get_items, get_highlights
from styles import inject_css
from utils import format_date

st.set_page_config(
    page_title="PKM — Knowledge Base",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# Run once per cold start. Safe to call every render — uses IF NOT EXISTS.
init_db()

# ─── Header ───────────────────────────────────────────────────────────────────

st.markdown("""
<div style="margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #1e1f2e;">
    <h1 style="font-size:1.8rem;font-weight:700;color:#e8eaf0;margin:0 0 4px;">
        Personal Knowledge Base
    </h1>
    <p style="color:#525870;font-size:0.9rem;margin:0;">
        Capture fast. Surface insights. Connect ideas.
    </p>
</div>
""", unsafe_allow_html=True)

# ─── Stats row ────────────────────────────────────────────────────────────────

conn = get_conn()
stats = get_stats(conn)

col1, col2, col3, col4 = st.columns(4)

STAT_CARDS = [
    (col1, "Items",      stats["items"],      "#4a90d9", "Articles, books, podcasts, videos, notes"),
    (col2, "Highlights", stats["highlights"], "#2ecc71", "Quotes and passages you've clipped"),
    (col3, "Tags",       stats["tags"],       "#f39c12", "Unique tags across your whole library"),
    (col4, "Links",      stats["links"],      "#9b59b6", "Manual connections between items"),
]

for col, label, value, color, tooltip in STAT_CARDS:
    col.markdown(f"""
<div style="
    background:#1a1b26;
    border:1px solid #2a2b3d;
    border-top:3px solid {color};
    border-radius:10px;
    padding:18px 20px;
    box-shadow:0 2px 12px rgba(0,0,0,0.35);
">
    <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;
                letter-spacing:0.09em;color:#525870;margin-bottom:6px;">{label}</div>
    <div style="font-size:2.2rem;font-weight:700;color:#e8eaf0;line-height:1.1;">{value}</div>
    <div style="font-size:0.75rem;color:#525870;margin-top:6px;line-height:1.4;">{tooltip}</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ─── Recent captures ──────────────────────────────────────────────────────────

recent_items = get_items(conn, limit=5)
recent_highlights = get_highlights(conn, limit=5)
conn.close()

st.markdown("""
<div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;
            letter-spacing:0.09em;color:#525870;margin-bottom:12px;">
    Recently Captured
</div>
""", unsafe_allow_html=True)

left, right = st.columns(2)

with left:
    st.markdown("<div style='font-size:0.82rem;font-weight:600;color:#8b92a5;margin-bottom:8px;'>Items</div>", unsafe_allow_html=True)
    if not recent_items:
        st.info("No items yet. Use Capture to add your first one.")
    else:
        for item in recent_items:
            ct = item["content_type_name"] or "Unknown"
            date = format_date(item["created_at"])
            url_badge = (
                f'<a href="{item["url"]}" target="_blank" style="color:#4a90d9;font-size:0.72rem;'
                f'text-decoration:none;margin-left:6px;">↗</a>'
                if item.get("url") else ""
            )
            st.markdown(f"""
<div style="background:#1a1b26;border:1px solid #2a2b3d;border-radius:8px;
            padding:10px 14px;margin-bottom:6px;">
    <div style="font-size:0.88rem;font-weight:600;color:#e8eaf0;margin-bottom:3px;
                line-height:1.3;">{item['title']}{url_badge}</div>
    <div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap;">
        <span style="background:rgba(74,144,217,0.15);color:#7eb8f7;border-radius:4px;
                     padding:1px 6px;font-size:0.7rem;font-weight:600;">{ct}</span>
        <span style="color:#525870;font-size:0.75rem;">{date}</span>
    </div>
</div>
""", unsafe_allow_html=True)

with right:
    st.markdown("<div style='font-size:0.82rem;font-weight:600;color:#8b92a5;margin-bottom:8px;'>Highlights</div>", unsafe_allow_html=True)
    if not recent_highlights:
        st.info("No highlights yet. Clip a quote from something you've read.")
    else:
        for h in recent_highlights:
            preview = h["text"][:90] + ("…" if len(h["text"]) > 90 else "")
            date = format_date(h["created_at"])
            source = h["source_info"] or ""
            st.markdown(f"""
<div style="background:#1a1b26;border:1px solid #2a2b3d;border-left:3px solid #4a90d9;
            border-radius:8px;padding:10px 14px;margin-bottom:6px;">
    <div style="font-size:0.85rem;color:#e8eaf0;line-height:1.45;font-style:italic;
                margin-bottom:4px;">"{preview}"</div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        {"<span style='color:#8b92a5;font-size:0.75rem;'>— " + source + "</span>" if source else ""}
        <span style="color:#525870;font-size:0.72rem;">{date}</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# ─── Quick navigation ─────────────────────────────────────────────────────────

st.markdown("""
<div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;
            letter-spacing:0.09em;color:#525870;margin-bottom:16px;">
    Where do you want to go?
</div>
""", unsafe_allow_html=True)

NAV_CARDS = [
    ("pages/1_Capture.py",  "Capture",  "📥", "#4a90d9",  "Add an item, paste a highlight, or drop a fleeting thought."),
    ("pages/2_Library.py",  "Library",  "📚", "#2ecc71",  "Search, filter by type or tag, and read what you've saved."),
    ("pages/7_SR_Review.py","Review",   "🧠", "#f39c12",  "Spaced repetition — review highlights at the right moment."),
    ("pages/6_Reader.py",   "Reader",   "📖", "#9b59b6",  "Read articles in a clean, focused view and clip highlights."),
]

nav_cols = st.columns(4)
for col, (page, label, icon, color, desc) in zip(nav_cols, NAV_CARDS):
    with col:
        st.markdown(f"""
<div style="
    background:#1a1b26;
    border:1px solid #2a2b3d;
    border-top:2px solid {color};
    border-radius:10px;
    padding:18px 16px 14px;
    margin-bottom:6px;
">
    <div style="font-size:1.5rem;margin-bottom:8px;">{icon}</div>
    <div style="font-size:0.95rem;font-weight:600;color:#e8eaf0;margin-bottom:4px;">{label}</div>
    <div style="font-size:0.78rem;color:#525870;line-height:1.45;">{desc}</div>
</div>
""", unsafe_allow_html=True)
        st.page_link(page, label=f"Open {label} →")
