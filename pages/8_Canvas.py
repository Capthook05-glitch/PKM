"""
pages/8_Canvas.py — Idea canvas / knowledge board (Heptabase style).

Create named canvases (think whiteboards or project spaces). Add items from
your library to a canvas and organise them into named clusters (columns).
Each card can have a colour and a private canvas note.

Use canvases to:
  - Organise items for a client presentation or consulting project
  - Map out a therapy model (e.g. cluster by CBT phase)
  - Build a reading list around a theme
  - Explore connections before writing or presenting

Clusters are free-form columns: A, B, C, D, E by default, but you can
rename them anything (Activation / Avoidance / Action, Trigger / Thought /
Behaviour, etc.).
"""

import streamlit as st

from styles import inject_css
from database import (
    add_item_to_canvas,
    create_canvas,
    delete_canvas,
    get_canvas_items,
    get_canvases,
    get_conn,
    get_items,
    init_db,
    move_canvas_item_cluster,
    remove_item_from_canvas,
    update_canvas_item_note,
)
from utils import format_date

st.set_page_config(page_title="Canvas", layout="wide")

inject_css()
init_db()

st.markdown("""
<div style="margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #1e1f2e;">
    <h1 style="font-size:1.75rem;font-weight:700;color:#e8eaf0;margin:0 0 4px;">Canvas</h1>
    <p style="color:#525870;font-size:0.875rem;margin:0;">
        Organise your ideas into named boards. Think in clusters, not just lists.
    </p>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar: canvas management ────────────────────────────────────────────────

with st.sidebar:
    st.header("Canvases")

    conn = get_conn()
    canvases = get_canvases(conn)
    conn.close()

    if not canvases:
        st.info("No canvases yet. Create one below.")
        selected_canvas_id = None
        selected_canvas = None
    else:
        canvas_opts = {c["name"]: c["id"] for c in canvases}
        selected_name = st.selectbox("Open canvas", list(canvas_opts.keys()), key="canvas_select")
        selected_canvas_id = canvas_opts[selected_name]
        selected_canvas = next(c for c in canvases if c["id"] == selected_canvas_id)

    st.markdown("---")
    st.subheader("New canvas")
    new_name = st.text_input("Name", key="new_canvas_name", placeholder="e.g. CBT Anxiety Model")
    new_desc = st.text_input("Description (optional)", key="new_canvas_desc", placeholder="What is this board for?")
    if st.button("Create canvas", key="create_canvas_btn", use_container_width=True):
        if new_name.strip():
            conn = get_conn()
            new_id = create_canvas(conn, new_name.strip(), new_desc.strip())
            conn.close()
            st.session_state.pop("new_canvas_name", None)
            st.session_state.pop("new_canvas_desc", None)
            st.session_state["canvas_select"] = new_name.strip()
            st.rerun()
        else:
            st.error("Enter a canvas name.")

    if selected_canvas_id:
        st.markdown("---")
        if st.button("Delete this canvas", key="del_canvas_btn", type="secondary"):
            st.session_state["confirm_del_canvas"] = selected_canvas_id

        if st.session_state.get("confirm_del_canvas") == selected_canvas_id:
            st.warning(f'Delete "{selected_name}"? All cards will be removed.')
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete", key="yes_del_canvas", type="primary"):
                conn = get_conn()
                delete_canvas(conn, selected_canvas_id)
                conn.close()
                st.session_state.pop("confirm_del_canvas", None)
                st.rerun()
            if c2.button("Cancel", key="no_del_canvas"):
                st.session_state.pop("confirm_del_canvas", None)
                st.rerun()

# ─── Main area ─────────────────────────────────────────────────────────────────

if not selected_canvas_id:
    st.info("Create a canvas from the sidebar to get started.")
    st.stop()

# Load canvas items
conn = get_conn()
canvas_rows = get_canvas_items(conn, selected_canvas_id)
all_items = get_items(conn)
conn.close()

canvas_item_ids = {row["item_id"] for row in canvas_rows}

# ─── Canvas header ─────────────────────────────────────────────────────────────

st.subheader(selected_canvas["name"])
if selected_canvas["description"]:
    st.caption(selected_canvas["description"])

# ─── Cluster name editor ───────────────────────────────────────────────────────

CLUSTER_KEYS = ["A", "B", "C", "D", "E"]

with st.expander("Rename clusters"):
    st.caption(
        "Give your clusters meaningful names. These labels appear as column headers. "
        "Renaming here is visual only — the underlying key (A–E) stays the same."
    )
    cluster_cols = st.columns(5)
    cluster_labels: dict[str, str] = {}
    for i, key in enumerate(CLUSTER_KEYS):
        with cluster_cols[i]:
            label = st.text_input(
                f"Cluster {key}",
                value=st.session_state.get(f"cluster_label_{key}", key),
                key=f"cluster_label_input_{key}",
                label_visibility="collapsed",
                placeholder=key,
            )
            cluster_labels[key] = label or key
            st.session_state[f"cluster_label_{key}"] = label or key

# ─── Add items to canvas ───────────────────────────────────────────────────────

with st.expander("Add items to this canvas"):
    available = [i for i in all_items if i["id"] not in canvas_item_ids]
    if not available:
        st.info("All library items are already on this canvas.")
    else:
        item_opts = {f"{i['title']}  [{i['content_type_name'] or '?'}]": i["id"] for i in available}
        add_cols = st.columns([4, 2, 2, 1])
        with add_cols[0]:
            sel_item_label = st.selectbox("Item", list(item_opts.keys()), key="add_canvas_item", label_visibility="collapsed")
        with add_cols[1]:
            sel_cluster = st.selectbox(
                "Cluster",
                [f"{k} – {cluster_labels[k]}" for k in CLUSTER_KEYS],
                key="add_canvas_cluster",
                label_visibility="collapsed",
            )
            sel_cluster_key = sel_cluster.split(" – ")[0]
        with add_cols[2]:
            color_opts = {"Blue": "blue", "Green": "green", "Orange": "orange", "Red": "red", "Purple": "purple", "Grey": "grey"}
            sel_color_label = st.selectbox("Color", list(color_opts.keys()), key="add_canvas_color", label_visibility="collapsed")
            sel_color = color_opts[sel_color_label]
        with add_cols[3]:
            st.write("")
            st.write("")
            if st.button("Add", key="add_canvas_btn", use_container_width=True):
                conn = get_conn()
                add_item_to_canvas(conn, selected_canvas_id, item_opts[sel_item_label], sel_cluster_key, sel_color)
                conn.close()
                st.rerun()

st.markdown("---")

# ─── Canvas board ──────────────────────────────────────────────────────────────

if not canvas_rows:
    st.markdown("""
<div style="
    text-align:center;
    padding:56px 40px;
    background:#1a1b26;
    border:1px dashed #2a2b3d;
    border-radius:12px;
    margin:24px 0;
">
    <div style="font-size:2.4rem;margin-bottom:12px;">🗂️</div>
    <div style="font-size:1rem;font-weight:600;color:#e8eaf0;margin-bottom:8px;">
        This canvas is empty
    </div>
    <div style="font-size:0.875rem;color:#525870;max-width:360px;margin:0 auto;">
        Open "Add items to this canvas" above to place your first card on the board.
    </div>
</div>
""", unsafe_allow_html=True)
    st.stop()

# Group by cluster
clusters: dict[str, list] = {k: [] for k in CLUSTER_KEYS}
for row in canvas_rows:
    key = row["cluster"] if row["cluster"] in CLUSTER_KEYS else "A"
    clusters[key].append(row)

# Only show non-empty clusters
active_keys = [k for k in CLUSTER_KEYS if clusters[k]]

if not active_keys:
    st.info("No items placed yet.")
    st.stop()

board_cols = st.columns(len(active_keys))

# ─── Card colour mapping ───────────────────────────────────────────────────────

COLOR_BG = {
    "blue":   "#0f2540",
    "green":  "#0f2d1e",
    "orange": "#2e1d06",
    "red":    "#2e1010",
    "purple": "#1e1030",
    "grey":   "#1e1e28",
}
COLOR_BORDER = {
    "blue":   "#4A90D9",
    "green":  "#2ECC71",
    "orange": "#F39C12",
    "red":    "#E74C3C",
    "purple": "#9B59B6",
    "grey":   "#7F8C8D",
}

CLUSTER_ACCENT_COLORS = {
    "A": "#4a90d9",
    "B": "#2ecc71",
    "C": "#f39c12",
    "D": "#9b59b6",
    "E": "#e74c3c",
}

for col_widget, cluster_key in zip(board_cols, active_keys):
    with col_widget:
        label = cluster_labels.get(cluster_key, cluster_key)
        count = len(clusters[cluster_key])
        accent = CLUSTER_ACCENT_COLORS.get(cluster_key, "#4a90d9")

        st.markdown(f"""
<div style="
    border-bottom:2px solid {accent};
    padding-bottom:9px;
    margin-bottom:14px;
    display:flex;
    align-items:baseline;
    justify-content:space-between;
">
    <span style="font-size:0.9rem;font-weight:700;color:#e8eaf0;letter-spacing:-0.01em;">{label}</span>
    <span style="font-size:0.72rem;color:{accent};font-weight:700;
                 background:rgba(74,144,217,0.1);
                 padding:2px 8px;border-radius:10px;">{count}</span>
</div>
""", unsafe_allow_html=True)

        for row in clusters[cluster_key]:
            cid = row["canvas_item_id"]
            color = row["color"] or "blue"
            bg = COLOR_BG.get(color, "#0f2540")
            border = COLOR_BORDER.get(color, "#4A90D9")

            # Card HTML
            title_safe = row["title"].replace('"', "&quot;")
            summary_short = (row["ai_summary"] or row["body"] or "")[:120]
            summary_html = (
                f'<p style="margin:6px 0 0;font-size:0.78rem;color:#8b92a5;line-height:1.45;">'
                f'{summary_short}{"…" if len(summary_short) == 120 else ""}</p>'
            ) if summary_short else ""

            note_html = ""
            if row.get("note"):
                note_preview = row["note"][:70] + ("…" if len(row["note"]) > 70 else "")
                note_html = (
                    f'<p style="margin:5px 0 0;font-size:0.75rem;color:#7eb8f7;font-style:italic;">'
                    f'{note_preview}</p>'
                )

            rating_html = (
                f'<span style="color:{border};font-size:0.72rem;font-weight:600;margin-left:5px;">'
                f'{"★" * row["impact_rating"]}</span>'
            ) if row.get("impact_rating") else ""

            ct_name = row["content_type_name"] or ""

            card_html = f"""
<div style="
    background:{bg};
    border:1px solid {border}44;
    border-top:3px solid {border};
    border-radius:8px;
    padding:12px 14px;
    margin-bottom:8px;
    box-shadow:0 2px 8px rgba(0,0,0,0.3);
">
    <div style="font-size:0.875rem;font-weight:600;color:#eee;line-height:1.35;margin-bottom:4px;">
        {title_safe}
    </div>
    <div style="font-size:0.72rem;color:{border};font-weight:600;
                text-transform:uppercase;letter-spacing:0.05em;">
        {ct_name}{rating_html}
    </div>
    {summary_html}{note_html}
</div>
"""
            st.markdown(card_html, unsafe_allow_html=True)

            # Controls (collapsed by default)
            with st.expander("Edit card", expanded=False):
                # Canvas note
                note_val = st.text_area(
                    "Canvas note",
                    value=row["note"] or "",
                    key=f"note_{cid}",
                    height=70,
                    placeholder="Why is this here? What does it connect to?",
                )
                color_opts2 = {"Blue": "blue", "Green": "green", "Orange": "orange", "Red": "red", "Purple": "purple", "Grey": "grey"}
                color_val = st.selectbox(
                    "Color",
                    list(color_opts2.keys()),
                    index=list(color_opts2.values()).index(color) if color in color_opts2.values() else 0,
                    key=f"color_{cid}",
                )
                if st.button("Save note & color", key=f"save_note_{cid}", use_container_width=True):
                    conn = get_conn()
                    update_canvas_item_note(conn, cid, note_val, color_opts2[color_val])
                    conn.close()
                    st.rerun()

                st.markdown("---")
                # Move to another cluster
                other_keys = [k for k in CLUSTER_KEYS if k != cluster_key]
                move_opts = [f"{k} – {cluster_labels[k]}" for k in other_keys]
                if move_opts:
                    move_target = st.selectbox("Move to cluster", move_opts, key=f"move_{cid}")
                    if st.button("Move", key=f"move_btn_{cid}", use_container_width=True):
                        target_key = move_target.split(" – ")[0]
                        conn = get_conn()
                        move_canvas_item_cluster(conn, cid, target_key)
                        conn.close()
                        st.rerun()

                if st.button("Remove from canvas", key=f"rm_{cid}", type="secondary", use_container_width=True):
                    conn = get_conn()
                    remove_item_from_canvas(conn, selected_canvas_id, row["item_id"])
                    conn.close()
                    st.rerun()
