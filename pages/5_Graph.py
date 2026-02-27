"""
pages/5_Graph.py — Interactive visual knowledge graph.

Every item in your library is a node. Every manual link you've created
is a directed edge. Nodes are colour-coded by content type and sized by
the number of connections they have.

Hover a node to see its title, type, and tags.
Use the sidebar to filter by tag or highlight isolated items.

Requires: pyvis>=0.3.2  (pip install pyvis)
"""

import os
import tempfile

import streamlit as st
import streamlit.components.v1 as components

from styles import inject_css
from database import (
    get_conn,
    get_graph_data,
    get_tags_for_items_batch,
    init_db,
)

st.set_page_config(page_title="Knowledge Graph", layout="wide")

inject_css()
init_db()

st.title("Knowledge Graph")
st.caption("Your items as nodes, your manual links as edges. Hover nodes to inspect. Drag to explore.")

# ─── Load data ────────────────────────────────────────────────────────────────

conn = get_conn()
items, links = get_graph_data(conn)
item_ids = [i["id"] for i in items]
tags_map = get_tags_for_items_batch(conn, item_ids)
conn.close()

if not items:
    st.info("Your library is empty. Head to **Capture** to add items, then create links in the **Library** to build your graph.")
    st.stop()

# ─── Sidebar controls ─────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Graph controls")

    # Collect all unique tags for the filter
    all_tags_in_graph: set = set()
    for tags in tags_map.values():
        all_tags_in_graph.update(tags)
    sorted_tags = sorted(all_tags_in_graph)

    tag_filter = st.selectbox(
        "Highlight by tag",
        ["All items"] + sorted_tags,
        key="graph_tag_filter",
    )

    show_isolated = st.checkbox(
        "Show isolated items (no links)",
        value=True,
        key="graph_show_isolated",
    )

    physics_on = st.checkbox(
        "Enable physics animation",
        value=True,
        key="graph_physics",
    )

    st.markdown("---")

    # Degree map for stats
    degree: dict = {i["id"]: 0 for i in items}
    for lnk in links:
        degree[lnk["source_id"]] = degree.get(lnk["source_id"], 0) + 1
        degree[lnk["target_id"]] = degree.get(lnk["target_id"], 0) + 1

    connected = sum(1 for d in degree.values() if d > 0)
    isolated = len(items) - connected

    st.markdown(f"**{len(items)}** items &nbsp;·&nbsp; **{len(links)}** connections")
    st.markdown(f"**{connected}** connected &nbsp;·&nbsp; **{isolated}** isolated")

    if links:
        top = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:5]
        id_to_title = {i["id"]: i["title"] for i in items}
        st.markdown("---")
        st.markdown("**Most connected:**")
        for nid, deg in top:
            if deg > 0:
                title = id_to_title.get(nid, "?")
                short = title[:30] + "…" if len(title) > 30 else title
                st.markdown(f"- **{short}** &nbsp; `{deg} links`")
    else:
        st.info("No links yet. Open any item in the Library and use the **Links** section to connect items.")

# ─── Build pyvis network ──────────────────────────────────────────────────────

try:
    from pyvis.network import Network
except ImportError:
    st.error(
        "pyvis is not installed. Run `pip install pyvis>=0.3.2` then restart the app."
    )
    st.stop()

# Content type → colour
CT_COLORS = {
    "Article":       "#4A90D9",
    "Book":          "#9B59B6",
    "Podcast":       "#F39C12",
    "Video":         "#E74C3C",
    "Note / Thought":"#27AE60",
    "Fleeting Note": "#7F8C8D",
}
DEFAULT_COLOR = "#BDC3C7"
HIGHLIGHT_COLOR = "#F1C40F"   # gold — used when a tag filter is active
DIM_COLOR = "#3D3D3D"         # dark grey for items that don't match the filter

net = Network(
    height="660px",
    width="100%",
    bgcolor="#0E1117",   # match Streamlit dark background
    font_color="#ECEFF1",
    directed=True,
    notebook=False,
)

if physics_on:
    net.barnes_hut(
        gravity=-6000,
        central_gravity=0.25,
        spring_length=180,
        spring_strength=0.05,
        damping=0.09,
    )
else:
    net.toggle_physics(False)

# Determine which item ids match the tag filter
if tag_filter == "All items":
    matched_ids = set(item_ids)
else:
    matched_ids = {iid for iid, tags in tags_map.items() if tag_filter in tags}

# Add nodes
for item in items:
    iid = item["id"]
    ct = item["content_type_name"] or "Unknown"
    tags = tags_map.get(iid, [])
    tag_str = ", ".join(tags) if tags else "no tags"
    deg = degree.get(iid, 0)

    # Skip isolated nodes if the user toggled them off
    if not show_isolated and deg == 0:
        continue

    # Node colour: gold if matched by tag filter, dim if not, type colour otherwise
    if tag_filter != "All items":
        color = HIGHLIGHT_COLOR if iid in matched_ids else DIM_COLOR
    else:
        color = CT_COLORS.get(ct, DEFAULT_COLOR)

    # Node size scales with degree (more links = bigger node)
    size = 14 + min(deg * 6, 36)

    # Truncate long labels
    label = item["title"] if len(item["title"]) <= 28 else item["title"][:25] + "…"

    # Hover tooltip (HTML)
    tooltip = (
        f"<b>{item['title']}</b><br/>"
        f"<i>{ct}</i><br/>"
        f"Tags: {tag_str}<br/>"
        f"Connections: {deg}"
    )

    net.add_node(
        iid,
        label=label,
        title=tooltip,
        color={"background": color, "border": color, "highlight": {"background": HIGHLIGHT_COLOR, "border": "#FFF"}},
        size=size,
        font={"size": 13, "color": "#ECEFF1"},
        borderWidth=2,
    )

# Add edges
node_ids_in_graph = {n["id"] for n in net.nodes}
for lnk in links:
    src, tgt = lnk["source_id"], lnk["target_id"]
    # Only add edge if both endpoints are in the graph (isolated-filter may have removed some)
    if src not in node_ids_in_graph or tgt not in node_ids_in_graph:
        continue
    rel = lnk["relationship_label"] or ""
    net.add_edge(
        src,
        tgt,
        title=rel,
        label=rel,
        arrows="to",
        color={"color": "#546E7A", "highlight": "#ECEFF1", "hover": "#90A4AE"},
        font={"size": 10, "color": "#90A4AE", "strokeWidth": 0},
        width=1.5,
        smooth={"type": "curvedCW", "roundness": 0.1},
    )

# ─── Render graph HTML ────────────────────────────────────────────────────────

tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
try:
    net.save_graph(tmp.name)
    tmp.close()
    with open(tmp.name, "r", encoding="utf-8") as f:
        graph_html = f.read()
finally:
    os.unlink(tmp.name)

# ─── Colour legend ────────────────────────────────────────────────────────────

legend_items = list(CT_COLORS.items()) + [("Other", DEFAULT_COLOR)]
cols = st.columns(len(legend_items))
for col, (label, color) in zip(cols, legend_items):
    col.markdown(
        f'<span style="color:{color}; font-size:18px;">●</span> '
        f'<span style="font-size:13px;">{label}</span>',
        unsafe_allow_html=True,
    )

st.markdown("")

# ─── Embed graph ──────────────────────────────────────────────────────────────

components.html(graph_html, height=670, scrolling=False)

st.caption(
    "Tip: scroll to zoom · drag nodes to rearrange · hover for details · "
    "links are created in the **Library** page under each item's **Links** section."
)
