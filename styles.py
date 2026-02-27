"""
styles.py — Global CSS injection for the PKM app.

Call inject_css() at the top of every page, right after st.set_page_config().
Provides a unified dark theme inspired by Heptabase/Readwise/Readwise Reader.
"""

import streamlit as st


def inject_css():
    st.markdown("""
<style>
/* ═══════════════════════════════════════════════════════
   FONTS
   ═══════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');

/* ═══════════════════════════════════════════════════════
   DESIGN TOKENS
   ═══════════════════════════════════════════════════════ */
:root {
    --bg-card:       #1a1b26;
    --bg-card-hover: #1f2133;
    --bg-sidebar:    #13141f;
    --border-card:   #2a2b3d;
    --border-subtle: #1e1f2e;
    --accent-blue:   #4a90d9;
    --accent-green:  #2ecc71;
    --accent-orange: #f39c12;
    --accent-red:    #e74c3c;
    --accent-purple: #9b59b6;
    --text-primary:  #e8eaf0;
    --text-secondary:#8b92a5;
    --text-muted:    #525870;
    --font-ui:       'Inter', system-ui, -apple-system, sans-serif;
    --font-reading:  'Lora', Georgia, serif;
    --radius-card:   10px;
    --radius-btn:    7px;
    --shadow-card:   0 2px 12px rgba(0,0,0,0.35);
}

/* ═══════════════════════════════════════════════════════
   GLOBAL TYPOGRAPHY
   ═══════════════════════════════════════════════════════ */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stMain"], .main .block-container {
    font-family: var(--font-ui) !important;
}

/* Heading hierarchy */
h1 { font-size: 1.75rem !important; font-weight: 700 !important; letter-spacing: -0.03em; color: var(--text-primary) !important; }
h2 { font-size: 1.35rem !important; font-weight: 600 !important; letter-spacing: -0.02em; color: var(--text-primary) !important; }
h3 { font-size: 1.1rem  !important; font-weight: 600 !important; color: var(--text-primary) !important; }
h4 { font-size: 0.95rem !important; font-weight: 600 !important; color: var(--text-secondary) !important; }

/* st.title / st.header / st.subheader */
[data-testid="stHeadingWithActionElements"] h1 { font-size: 1.75rem !important; font-weight: 700 !important; }
[data-testid="stHeadingWithActionElements"] h2 { font-size: 1.35rem !important; font-weight: 600 !important; }
[data-testid="stHeadingWithActionElements"] h3 { font-size: 1.1rem  !important; font-weight: 600 !important; }

/* st.caption */
[data-testid="stCaptionContainer"] p,
.stCaption p {
    color: var(--text-muted) !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.01em;
}

/* Markdown base text */
[data-testid="stMarkdownContainer"] p {
    color: var(--text-secondary);
    line-height: 1.65;
    font-size: 0.925rem;
}

/* Inline code / backtick tags */
[data-testid="stMarkdownContainer"] code,
code {
    background: rgba(74, 144, 217, 0.12) !important;
    color: #7eb8f7 !important;
    border-radius: 4px;
    padding: 1px 5px;
    font-size: 0.82em;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    border: none !important;
}

/* Blockquote (highlight text) */
blockquote {
    border-left: 3px solid var(--accent-blue) !important;
    padding: 8px 0 8px 16px !important;
    margin: 8px 0 !important;
}
blockquote p {
    color: var(--text-primary) !important;
    font-size: 1rem !important;
    line-height: 1.6;
}

/* ═══════════════════════════════════════════════════════
   SIDEBAR
   ═══════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background-color: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border-subtle) !important;
}

[data-testid="stSidebarContent"] {
    padding: 1.25rem 1rem !important;
}

/* Sidebar headings */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--text-muted) !important;
    margin-bottom: 0.6rem;
}

/* ═══════════════════════════════════════════════════════
   BUTTONS
   ═══════════════════════════════════════════════════════ */
[data-testid="stButton"] > button {
    border-radius: var(--radius-btn) !important;
    font-family: var(--font-ui) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    padding: 0.45rem 1rem !important;
    transition: opacity 0.15s, transform 0.1s, box-shadow 0.15s !important;
    cursor: pointer;
    letter-spacing: 0.01em;
}
[data-testid="stButton"] > button:hover {
    opacity: 0.88;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}
[data-testid="stButton"] > button:active {
    transform: translateY(0);
}

/* Primary button */
[data-testid="stButton"] > button[kind="primary"] {
    background: var(--accent-blue) !important;
    color: #fff !important;
    border: none !important;
}

/* Secondary button */
[data-testid="stButton"] > button[kind="secondary"] {
    background: rgba(255,255,255,0.05) !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border-card) !important;
}
[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: rgba(255,255,255,0.09) !important;
    color: var(--text-primary) !important;
}

/* Download button */
[data-testid="stDownloadButton"] > button {
    border-radius: var(--radius-btn) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
}

/* ═══════════════════════════════════════════════════════
   INPUTS
   ═══════════════════════════════════════════════════════ */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: var(--radius-btn) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-ui) !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s, box-shadow 0.15s;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 2px rgba(74,144,217,0.18) !important;
    outline: none !important;
}

/* Input labels */
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label {
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    color: var(--text-secondary) !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 3px !important;
}

/* Selectbox */
[data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: var(--radius-btn) !important;
    color: var(--text-primary) !important;
}

/* ═══════════════════════════════════════════════════════
   TABS
   ═══════════════════════════════════════════════════════ */
[data-testid="stTabs"] [data-testid="stTab"] {
    font-family: var(--font-ui) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: var(--text-muted) !important;
    padding: 8px 18px !important;
    transition: color 0.15s;
}
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
    color: var(--text-primary) !important;
    border-bottom: 2px solid var(--accent-blue) !important;
    background: transparent !important;
}
[data-testid="stTabs"] [data-testid="stTab"]:hover {
    color: var(--text-secondary) !important;
    background: rgba(255,255,255,0.03) !important;
}
[data-testid="stTabsContent"] {
    padding-top: 1rem !important;
}

/* ═══════════════════════════════════════════════════════
   EXPANDER — card appearance
   ═══════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: var(--radius-card) !important;
    box-shadow: var(--shadow-card) !important;
    margin-bottom: 10px !important;
    overflow: hidden;
    transition: border-color 0.15s;
}
[data-testid="stExpander"]:hover {
    border-color: rgba(74,144,217,0.35) !important;
}
[data-testid="stExpander"] summary {
    padding: 12px 16px !important;
    background: var(--bg-card) !important;
    font-family: var(--font-ui) !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    color: var(--text-primary) !important;
    cursor: pointer;
    user-select: none;
}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding: 0 16px 16px !important;
    border-top: 1px solid var(--border-subtle) !important;
}

/* ═══════════════════════════════════════════════════════
   CONTAINER WITH BORDER — st.container(border=True)
   ═══════════════════════════════════════════════════════ */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: var(--radius-card) !important;
    box-shadow: var(--shadow-card) !important;
    padding: 0 !important;
    overflow: hidden;
}
[data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] {
    padding: 20px 24px !important;
}

/* ═══════════════════════════════════════════════════════
   METRIC CARDS
   ═══════════════════════════════════════════════════════ */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: var(--radius-card) !important;
    padding: 16px 20px !important;
    box-shadow: var(--shadow-card) !important;
}
[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted) !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
    line-height: 1.15;
}

/* ═══════════════════════════════════════════════════════
   ALERTS / INFO / SUCCESS / WARNING
   ═══════════════════════════════════════════════════════ */
[data-testid="stAlert"] {
    border-radius: var(--radius-card) !important;
    font-size: 0.9rem !important;
}
[data-testid="stAlert"][kind="info"],
[data-testid="stNotification"][kind="info"] {
    background: rgba(74,144,217,0.08) !important;
    border: 1px solid rgba(74,144,217,0.3) !important;
}
[data-testid="stAlert"][kind="success"],
[data-testid="stNotification"][kind="success"] {
    background: rgba(46,204,113,0.08) !important;
    border: 1px solid rgba(46,204,113,0.3) !important;
}
[data-testid="stAlert"][kind="warning"],
[data-testid="stNotification"][kind="warning"] {
    background: rgba(243,156,18,0.08) !important;
    border: 1px solid rgba(243,156,18,0.3) !important;
}

/* ═══════════════════════════════════════════════════════
   PROGRESS BAR
   ═══════════════════════════════════════════════════════ */
[data-testid="stProgress"] {
    margin: 4px 0 !important;
}
[data-testid="stProgress"] > div {
    border-radius: 100px !important;
    background: rgba(255,255,255,0.07) !important;
    height: 5px !important;
    overflow: hidden;
}
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, var(--accent-blue), #7eb8f7) !important;
    border-radius: 100px !important;
    height: 5px !important;
    transition: width 0.4s cubic-bezier(0.4,0,0.2,1) !important;
}

/* ═══════════════════════════════════════════════════════
   DIVIDERS
   ═══════════════════════════════════════════════════════ */
hr {
    border: none !important;
    border-top: 1px solid var(--border-subtle) !important;
    margin: 1.25rem 0 !important;
}

/* ═══════════════════════════════════════════════════════
   FILE UPLOADER
   ═══════════════════════════════════════════════════════ */
[data-testid="stFileUploader"] {
    border: 1px dashed var(--border-card) !important;
    border-radius: var(--radius-card) !important;
    padding: 12px !important;
    background: rgba(255,255,255,0.02) !important;
}

/* ═══════════════════════════════════════════════════════
   TOGGLE / CHECKBOX
   ═══════════════════════════════════════════════════════ */
[data-testid="stCheckbox"] label p,
[data-testid="stToggle"] label p {
    font-size: 0.875rem !important;
    color: var(--text-secondary) !important;
}

/* ═══════════════════════════════════════════════════════
   SCROLLBAR (WebKit)
   ═══════════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-card); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* ═══════════════════════════════════════════════════════
   HIDE STREAMLIT CHROME
   ═══════════════════════════════════════════════════════ */
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stDecoration"] { display: none !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)
