"""
pages/4_Digest.py — Weekly digest and framework builder.

Two tabs:

  Weekly Digest      — Pick a time window (7 / 14 / 30 days). The AI reads
                       everything you captured in that window and produces a
                       structured reflection: themes, top insights, cross-item
                       connections, and open questions. Download as markdown.

  Build a Framework  — Select 3–10 items from your library. The AI synthesizes
                       them into a named, reusable mental model with components
                       and step-by-step application guidance. Download as
                       markdown to use with clients or share with teams.

Both tabs store their last result in session state so the page doesn't
re-run the AI on every interaction — only when you explicitly click Generate
or Build.
"""

import streamlit as st
from datetime import date

from styles import inject_css
from ai import build_framework, generate_weekly_digest
from database import (
    get_conn,
    get_items,
    get_tags_for_items_batch,
    get_weekly_captures,
    init_db,
)
from utils import digest_to_markdown, framework_to_markdown, safe_filename

st.set_page_config(page_title="Digest & Framework", layout="wide")

inject_css()
init_db()

st.markdown("""
<div style="margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #1e1f2e;">
    <h1 style="font-size:1.75rem;font-weight:700;color:#e8eaf0;margin:0 0 4px;">Digest & Framework</h1>
    <p style="color:#525870;font-size:0.875rem;margin:0;">Turn your captures into reflections and reusable tools.</p>
</div>
""", unsafe_allow_html=True)

tab_digest, tab_framework = st.tabs(["Weekly Digest", "Build a Framework"])


# ─── Weekly Digest tab ────────────────────────────────────────────────────────

with tab_digest:

    st.subheader("Weekly Digest")

    days_map = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30}
    selected_window = st.selectbox(
        "Time window",
        list(days_map.keys()),
        key="digest_window",
    )
    days = days_map[selected_window]

    # Load this window's captures
    conn = get_conn()
    items, highlights = get_weekly_captures(conn, days=days)
    item_ids = [i["id"] for i in items]
    item_tags_map = get_tags_for_items_batch(conn, item_ids)
    conn.close()

    total = len(items) + len(highlights)
    st.caption(f"**{len(items)} items** and **{len(highlights)} highlights** in the last {days} days.")

    if total == 0:
        st.info(
            f"Nothing captured in the last {days} days. "
            "Try a wider window, or head to Capture."
        )
    else:
        # Collapsible preview of what's included
        with st.expander(f"What's included ({total} captures)"):
            if items:
                st.markdown("**Items**")
                for item in items:
                    ct = item["content_type_name"] or "Unknown"
                    st.markdown(f"- **{item['title']}** `{ct}`")
            if highlights:
                st.markdown("**Highlights**")
                for h in highlights:
                    preview = h["text"][:80] + ("..." if len(h["text"]) > 80 else "")
                    st.markdown(f'- "{preview}"')

        # Generate button (always visible so user can regenerate)
        if st.button("Generate Digest", type="primary", key="gen_digest_btn"):
            with st.spinner("Generating your digest — this takes 10–20 seconds..."):
                try:
                    result = generate_weekly_digest(items, highlights, item_tags_map)
                    st.session_state["digest_result"] = result
                    st.session_state["digest_days"] = days
                except RuntimeError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"AI error: {e}")
            st.rerun()

        # Show result (persists until a new one is generated)
        digest_result = st.session_state.get("digest_result")
        if digest_result:
            st.markdown("---")
            st.markdown(digest_result)
            st.markdown("---")

            result_days = st.session_state.get("digest_days", days)
            md_export = digest_to_markdown(digest_result, days=result_days)
            today_str = date.today().isoformat()

            dl_col, clear_col = st.columns([1, 1])
            with dl_col:
                st.download_button(
                    "Download as Markdown",
                    data=md_export,
                    file_name=f"digest_{today_str}.md",
                    mime="text/markdown",
                    key="dl_digest_btn",
                )
            with clear_col:
                if st.button("Clear", key="clear_digest_btn"):
                    st.session_state.pop("digest_result", None)
                    st.session_state.pop("digest_days", None)
                    st.rerun()


# ─── Build a Framework tab ────────────────────────────────────────────────────

with tab_framework:

    st.subheader("Build a Framework")
    st.caption(
        "Select 3–10 items from your library. The AI will synthesize them into a named, "
        "reusable mental model — something you can use with clients or a team."
    )

    conn = get_conn()
    all_items = get_items(conn)
    all_ids = [i["id"] for i in all_items]
    all_tags_map = get_tags_for_items_batch(conn, all_ids)
    conn.close()

    if not all_items:
        st.info("Your library is empty. Capture some items first, then come back.")
    else:
        # Build display label → item mapping for the multiselect
        item_options: dict = {}
        for item in all_items:
            ct = item["content_type_name"] or "Unknown"
            # Include tags in label to help with selection
            tags = all_tags_map.get(item["id"], [])
            tag_hint = f"  [{', '.join(tags[:3])}]" if tags else ""
            label = f"{item['title']}  ({ct}){tag_hint}"
            item_options[label] = item

        selected_labels = st.multiselect(
            "Select items to synthesize",
            options=list(item_options.keys()),
            key="fw_selected",
            help="Choose items that feel related, complementary, or interestingly in tension. 3 minimum, 10 maximum.",
        )

        selected_items = [item_options[lbl] for lbl in selected_labels]
        n = len(selected_items)

        if n == 0:
            st.caption("Select at least 3 items to unlock the Build button.")
        elif n < 3:
            st.caption(f"{n} selected — need at least 3.")
        elif n > 10:
            st.warning("Select 10 or fewer items.")
        else:
            st.caption(f"{n} items selected. Ready to build.")

        build_ok = 3 <= n <= 10

        if st.button(
            "Build Framework",
            type="primary",
            key="build_fw_btn",
            disabled=not build_ok,
        ):
            with st.spinner(f"Synthesizing {n} items into a framework — 15–30 seconds..."):
                try:
                    result = build_framework(selected_items, item_tags_map=all_tags_map)
                    st.session_state["fw_result"] = result
                except RuntimeError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"AI error: {e}")
            st.rerun()

        # ── Show framework result ──────────────────────────────────────
        fw = st.session_state.get("fw_result")
        if fw:
            st.markdown("---")

            # Header
            st.markdown(f"## {fw['name']}")
            if fw.get("tagline"):
                st.markdown(f"*{fw['tagline']}*")
            st.markdown("")

            if fw.get("description"):
                st.markdown(fw["description"])

            # Components
            components = fw.get("components", [])
            if components:
                st.markdown("### Components")
                for comp in components:
                    with st.container(border=True):
                        st.markdown(f"**{comp.get('name', 'Component')}**")
                        if comp.get("description"):
                            st.markdown(comp["description"])
                        if comp.get("application"):
                            st.info(f"**In practice:** {comp['application']}")

            # How to apply
            if fw.get("how_to_use"):
                st.markdown("### How to Apply This Framework")
                st.markdown(fw["how_to_use"])

            # Source items
            if fw.get("source_items"):
                st.caption("Built from: " + "  ·  ".join(fw["source_items"]))

            st.markdown("---")

            # Download + clear
            md_export = framework_to_markdown(fw)
            fname = safe_filename(fw["name"]) or "framework"

            dl_col, clear_col = st.columns([1, 1])
            with dl_col:
                st.download_button(
                    "Download as Markdown",
                    data=md_export,
                    file_name=f"{fname}.md",
                    mime="text/markdown",
                    key="dl_fw_btn",
                )
            with clear_col:
                if st.button("Clear and start over", key="clear_fw_btn"):
                    st.session_state.pop("fw_result", None)
                    st.session_state.pop("fw_selected", None)
                    st.rerun()
