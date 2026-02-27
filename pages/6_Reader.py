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

from database import (
    add_highlight,
    get_conn,
    get_item_tags,
    get_items,
    init_db,
)
from utils import fetch_article_content, format_date, parse_tags

st.set_page_config(page_title="Reader", layout="wide")

init_db()

st.title("Reader")
st.caption("Read without distraction. Clip highlights as you go.")

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

# ─── Article content area ──────────────────────────────────────────────────────

ct = item["content_type_name"] or "Unknown"
tag_str = "  ".join(f"`{t}`" for t in item_tags) if item_tags else "*no tags*"

# Header
st.markdown(f"## {item['title']}")
st.caption(
    f"`{ct}` &nbsp;·&nbsp; {format_date(item['created_at'])}"
    + (f" &nbsp;·&nbsp; {tag_str}" if item_tags else "")
)

if item["url"]:
    st.markdown(f"[Open original]({item['url']})  ↗")

st.markdown("---")

# ── Main reading content ───────────────────────────────────────────────────────

if item["ai_summary"] or item["ai_insight"]:
    with st.expander("AI summary & insight", expanded=False):
        if item["ai_summary"]:
            st.markdown(f"**Summary:** {item['ai_summary']}")
        if item["ai_insight"]:
            st.info(f"**Actionable insight:** {item['ai_insight']}")

if item["url"]:
    # Fetch article
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
        # Render the article in a clean scrollable container
        # We split into paragraphs for readability
        paragraphs = [p for p in result["text"].split("\n\n") if p.strip()]

        col_read, col_pad = st.columns([3, 1])
        with col_read:
            for para in paragraphs:
                st.markdown(para)

elif item["body"]:
    col_read, col_pad = st.columns([3, 1])
    with col_read:
        st.markdown(item["body"])
else:
    st.info("No URL and no saved notes for this item. Edit it in the Library to add content.")

# ─── Clip a highlight ──────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Clip a highlight")
st.caption(
    "Select text in the article above, copy it, and paste it here. "
    "It will be saved as a highlight linked to this item."
)

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
