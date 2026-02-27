"""
pages/6_Reader.py — Distraction-free reading view (Readwise Reader style).

Pick any item that has a URL from the sidebar. The app fetches the full
article text and renders it in a clean reading view. While reading you can:

  - Clip a highlight: select text on the page, paste it into the Clip form,
    and save it directly to your highlights library linked to this item.
  - View the body / notes you've already saved for the item.
  - See AI summary and insight if the item has been processed.

Items without a URL show their saved body text instead.
"""

import streamlit as st

from styles import inject_css
from database import (
    add_highlight,
    get_conn,
    get_item_tags,
    get_items,
    init_db,
)
from utils import fetch_article_content, format_date, parse_tags

st.set_page_config(page_title="Reader", layout="wide")

inject_css()

# Reading-specific typography override
st.markdown("""
<style>
/* Article body paragraphs — constrain width + Lora font */
.reading-body p {
    font-family: 'Lora', Georgia, serif !important;
    font-size: 1.08rem !important;
    line-height: 1.78 !important;
    color: #d5d8e8 !important;
    max-width: 70ch;
}
/* Target the reading column's markdown containers */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child
    [data-testid="stMarkdownContainer"] p {
    font-family: 'Lora', Georgia, serif !important;
    font-size: 1.06rem !important;
    line-height: 1.78 !important;
    color: #d5d8e8 !important;
    max-width: 70ch;
}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child
    [data-testid="stMarkdownContainer"] h1,
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child
    [data-testid="stMarkdownContainer"] h2,
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child
    [data-testid="stMarkdownContainer"] h3 {
    font-family: 'Inter', sans-serif !important;
    color: #e8eaf0 !important;
}
</style>
""", unsafe_allow_html=True)

init_db()

st.markdown("""
<div style="margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #1e1f2e;">
    <h1 style="font-size:1.75rem;font-weight:700;color:#e8eaf0;margin:0 0 4px;">Reader</h1>
    <p style="color:#525870;font-size:0.875rem;margin:0;">
        Read without distraction. Clip highlights as you go.
    </p>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar: item selector ────────────────────────────────────────────────────

with st.sidebar:
    st.header("Your library")

    search = st.text_input("Search items", placeholder="keyword...", key="reader_search")

    conn = get_conn()
    all_items = get_items(conn, search=search or None)
    conn.close()

    url_items = [i for i in all_items if i["url"]]
    no_url_items = [i for i in all_items if not i["url"]]

    if not all_items:
        st.info("No items yet. Add some from Capture.")
        st.stop()

    option_labels = {}
    for item in url_items:
        ct = item["content_type_name"] or "Unknown"
        option_labels[f"[URL] {item['title']}  ({ct})"] = item["id"]
    for item in no_url_items:
        ct = item["content_type_name"] or "Unknown"
        option_labels[f"{item['title']}  ({ct})"] = item["id"]

    selected_label = st.selectbox(
        "Select item to read",
        list(option_labels.keys()),
        key="reader_item",
    )
    selected_id = option_labels[selected_label]

    st.markdown("---")
    st.caption("Items marked [URL] will be fetched from the web. Others show saved notes.")

# ─── Load selected item ────────────────────────────────────────────────────────

conn = get_conn()
item = conn.execute(
    """
    SELECT i.*, ct.name AS content_type_name
    FROM items i
    LEFT JOIN content_types ct ON ct.id = i.content_type_id
    WHERE i.id = ?
    """,
    (selected_id,),
).fetchone()
item_tags = get_item_tags(conn, selected_id)
conn.close()

if not item:
    st.error("Item not found.")
    st.stop()

# ─── Article header ────────────────────────────────────────────────────────────

ct = item["content_type_name"] or "Unknown"

tag_pill_str = "".join(
    f'<span style="background:rgba(74,144,217,0.12);color:#7eb8f7;border-radius:4px;'
    f'padding:2px 7px;font-size:0.77rem;margin-right:5px;display:inline-block;">{t}</span>'
    for t in item_tags
) if item_tags else ""

url_link = (
    f'<a href="{item["url"]}" target="_blank" style="color:#4a90d9;font-size:0.85rem;'
    f'text-decoration:none;">Open original ↗</a>'
    if item["url"] else ""
)

st.markdown(f"""
<div style="margin-bottom:24px;padding-bottom:18px;border-bottom:1px solid #1e1f2e;">
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
                letter-spacing:0.08em;color:#525870;margin-bottom:8px;">
        {ct} &nbsp;·&nbsp; {format_date(item['created_at'])}
    </div>
    <h1 style="font-size:1.55rem;font-weight:700;color:#e8eaf0;
               line-height:1.25;margin:0 0 10px 0;">{item['title']}</h1>
    {"<div style='margin-bottom:10px;'>" + tag_pill_str + "</div>" if tag_pill_str else ""}
    {url_link}
</div>
""", unsafe_allow_html=True)

# ─── AI summary ────────────────────────────────────────────────────────────────

if item["ai_summary"] or item["ai_insight"]:
    with st.expander("AI summary & insight", expanded=False):
        if item["ai_summary"]:
            st.markdown(f"**Summary:** {item['ai_summary']}")
        if item["ai_insight"]:
            st.info(f"**Actionable insight:** {item['ai_insight']}")

# ─── Main reading content ──────────────────────────────────────────────────────

if item["url"]:
    cache_key = f"reader_content_{selected_id}"

    if cache_key not in st.session_state:
        with st.spinner("Fetching article…"):
            result = fetch_article_content(item["url"])
        st.session_state[cache_key] = result

    result = st.session_state[cache_key]

    if result["error"]:
        st.warning(f"Could not fetch the article: {result['error']}")
        if item["body"]:
            st.markdown("Showing saved notes instead:")
            st.markdown(item["body"])
    else:
        total_chars = len(result["text"])
        paragraphs = [p for p in result["text"].split("\n\n") if p.strip()]

        # Reading progress bar
        read_key = f"reader_pos_{selected_id}"
        pos = st.session_state.get(read_key, 0)
        pct = min(pos / max(total_chars, 1), 1.0)

        st.markdown(f"""
<div style="margin-bottom:16px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
        <span style="font-size:0.7rem;font-weight:700;text-transform:uppercase;
                     letter-spacing:0.07em;color:#525870;">Reading progress</span>
        <span style="font-size:0.75rem;color:#4a90d9;font-weight:600;">
            {int(pct*100)}%
        </span>
    </div>
    <div style="height:4px;background:#1e1f2e;border-radius:100px;overflow:hidden;">
        <div style="width:{pct*100:.1f}%;height:4px;
                    background:linear-gradient(90deg,#4a90d9,#7eb8f7);
                    border-radius:100px;transition:width 0.3s;"></div>
    </div>
</div>
""", unsafe_allow_html=True)

        col_read, col_pad = st.columns([3, 1])
        with col_read:
            for para in paragraphs:
                st.markdown(para)

        # Mark progress button at end of article
        if st.button("Mark as read", key=f"mark_read_{selected_id}", type="secondary"):
            st.session_state[read_key] = total_chars
            st.rerun()

elif item["body"]:
    col_read, col_pad = st.columns([3, 1])
    with col_read:
        st.markdown(item["body"])
else:
    st.info("No URL and no saved notes for this item. Edit it in the Library to add content.")

# ─── Clip a highlight ──────────────────────────────────────────────────────────

st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""
<div style="
    background:rgba(74,144,217,0.08);
    border:1px solid rgba(74,144,217,0.25);
    border-radius:8px;
    padding:10px 16px;
    margin-bottom:16px;
    display:flex;
    align-items:center;
    gap:10px;
">
    <span style="font-size:1.1rem;">✂️</span>
    <span style="font-size:0.875rem;color:#7eb8f7;">
        Select text in the article, copy it (Ctrl+C / Cmd+C), then paste it below to save as a highlight.
    </span>
</div>
""", unsafe_allow_html=True)

st.subheader("Clip a highlight")

if st.session_state.get("clip_saved_msg"):
    st.success(st.session_state.pop("clip_saved_msg"))

clip_text = st.text_area(
    "Paste the text you want to highlight *",
    key="clip_text",
    height=120,
    placeholder="Paste selected text here…",
)

clip_source = st.text_input(
    "Source detail (optional)",
    key="clip_source",
    placeholder='e.g. "paragraph 3" or "under the subheading Goals"',
)

clip_tags = st.text_input(
    "Tags (comma-separated, optional)",
    key="clip_tags",
    placeholder="insight, reframe",
)

if st.button("Save highlight", type="primary", key="clip_save_btn"):
    text = st.session_state.get("clip_text", "").strip()
    if not text:
        st.error("Paste some text first.")
    else:
        source = st.session_state.get("clip_source", "").strip() or item["title"]
        tag_list = parse_tags(st.session_state.get("clip_tags", ""))
        conn = get_conn()
        h_id = add_highlight(
            conn,
            text=text,
            source_info=source or None,
            parent_item_id=selected_id,
            tag_names=tag_list,
        )
        conn.close()
        for k in ["clip_text", "clip_source", "clip_tags"]:
            st.session_state.pop(k, None)
        preview = text[:60] + ("..." if len(text) > 60 else "")
        st.session_state["clip_saved_msg"] = f'Highlight saved: "{preview}"'
        st.rerun()
