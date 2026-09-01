"""Visual themes.

Kept deliberately plain: solid backgrounds, one border weight, no gradients
or animation. Every colour is published as a CSS custom property so the bulk
of the stylesheet below is a static string, and swapping themes only rewrites
the small ``:root`` block.
"""

from __future__ import annotations

import streamlit as st

from ..config import LEGACY_THEME_MAP, THEME_OPTIONS

PALETTES = {
    "Ocean Slate": {
        "accent": "#0ea5e9",
        "bg": "#f7f9fc",
        "text": "#0f172a",
        "muted": "#64748b",
        "card": "#ffffff",
        "sidebar": "#ffffff",
        "border": "#e2e8f0",
        "btn_text": "#ffffff",
        "is_dark": False,
    },
    "Midnight Indigo": {
        "accent": "#818cf8",
        "bg": "#11141f",
        "text": "#e8eaf0",
        "muted": "#9aa3b8",
        "card": "#181c2b",
        "sidebar": "#14172423",
        "border": "#2a2f42",
        "btn_text": "#0f1120",
        "is_dark": True,
    },
    "Warm Ember": {
        "accent": "#f97316",
        "bg": "#1b1512",
        "text": "#faf5f0",
        "muted": "#c4b5a8",
        "card": "#241c18",
        "sidebar": "#241c18",
        "border": "#3a2c24",
        "btn_text": "#1b1512",
        "is_dark": True,
    },
}

# Chip colours differ between light and dark so text keeps a readable contrast
# ratio against its tinted background. Every status/priority uses one of five
# plain, low-saturation tints - no per-theme gradients.
_DARK_CHIPS = {
    "chip_bg": "#242938",
    "chip_text": "#cbd5e1",
    "high": ("#3a2226", "#f5a3a3"),
    "medium": ("#3a3220", "#f0cf7a"),
    "low": ("#1f3327", "#8fd6ab"),
    "pending": ("#242938", "#a5b4fc"),
    "progress": ("#1c2e3a", "#7dd3fc"),
    "completed": ("#1f3327", "#8fd6ab"),
    "archived": ("#242938", "#94a3b8"),
}

_LIGHT_CHIPS = {
    "chip_bg": "#f1f5f9",
    "chip_text": "#334155",
    "high": ("#fdecec", "#b91c1c"),
    "medium": ("#fdf6e3", "#92610a"),
    "low": ("#eaf7ee", "#15803d"),
    "pending": ("#eef1fd", "#4338ca"),
    "progress": ("#eaf4fd", "#1d4ed8"),
    "completed": ("#eaf7ee", "#166534"),
    "archived": ("#f1f5f9", "#475569"),
}

_STATIC_CSS = """
html, body, [class*="css"] {
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}

.stApp {
    background: var(--tm-bg);
    color: var(--tm-text);
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2.5rem;
    max-width: 1080px;
}

h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {
    color: var(--tm-text);
}

[data-testid="stSidebar"] {
    background: var(--tm-sidebar) !important;
    border-right: 1px solid var(--tm-border);
}

[data-testid="stMetric"], div[data-testid="stExpander"], div[data-testid="stForm"] {
    background: var(--tm-card);
    border: 1px solid var(--tm-border);
    border-radius: 10px;
}

[data-testid="stMetric"] { padding: 0.75rem 0.9rem; }
div[data-testid="stForm"] { padding: 1rem 1.15rem; }

[data-testid="stMetricLabel"] { color: var(--tm-muted) !important; font-size: 0.8rem !important; }
[data-testid="stMetricValue"] { color: var(--tm-text) !important; font-weight: 600 !important; }

.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div, .stDateInput input {
    border-radius: 8px !important;
    border-color: var(--tm-border) !important;
    background: var(--tm-card) !important;
    color: var(--tm-text) !important;
}

.stButton > button {
    border-radius: 8px !important;
    border: 1px solid var(--tm-accent) !important;
    background: var(--tm-accent) !important;
    color: var(--tm-btn-text) !important;
    font-weight: 500 !important;
    padding: 0.4rem 1rem !important;
}

.stButton > button:hover { filter: brightness(1.08); }

.stButton > button:focus-visible {
    outline: 2px solid var(--tm-accent) !important;
    outline-offset: 2px !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
    background: transparent;
    border-bottom: 1px solid var(--tm-border);
    flex-wrap: wrap;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 6px 6px 0 0 !important;
    padding: 0.45rem 0.85rem !important;
    background: transparent !important;
    color: var(--tm-muted) !important;
    font-weight: 500 !important;
    border: none !important;
}

.stTabs [aria-selected="true"] {
    color: var(--tm-accent) !important;
    font-weight: 600 !important;
    border-bottom: 2px solid var(--tm-accent) !important;
}

.stProgress > div > div { background: var(--tm-accent) !important; border-radius: 999px !important; }
.stProgress > div { background: var(--tm-border) !important; border-radius: 999px !important; }

/* Custom components */
.tm-hero {
    background: var(--tm-card);
    border: 1px solid var(--tm-border);
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 1rem;
}

.tm-hero .tm-welcome { margin: 0; color: var(--tm-text); font-size: 0.95rem; }

.tm-auth-shell {
    max-width: 480px;
    margin: 2rem auto 0;
    padding: 1.75rem 2rem;
    background: var(--tm-card);
    border: 1px solid var(--tm-border);
    border-radius: 10px;
}

.tm-auth-shell h1 { text-align: center; margin-bottom: 0.25rem; color: var(--tm-text); }

.tm-auth-sub {
    text-align: center;
    color: var(--tm-muted);
    margin-bottom: 1.25rem;
    font-size: 0.9rem;
}

.tm-kpi-wrap {
    display: grid;
    grid-template-columns: repeat(6, minmax(100px, 1fr));
    gap: 0.5rem;
    margin: 0.9rem 0 1.1rem;
}

@media (max-width: 900px) { .tm-kpi-wrap { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 520px) { .tm-kpi-wrap { grid-template-columns: repeat(2, 1fr); } }

.tm-kpi {
    background: var(--tm-card);
    border: 1px solid var(--tm-border);
    border-radius: 8px;
    padding: 0.7rem 0.8rem;
}

.tm-kpi .label {
    font-size: 0.72rem;
    color: var(--tm-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
}

.tm-kpi .value { font-size: 1.35rem; font-weight: 600; margin-top: 0.15rem; color: var(--tm-text); }

.tm-card {
    background: var(--tm-card);
    border: 1px solid var(--tm-border);
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.65rem;
}

.tm-card strong { color: var(--tm-text); }

.tm-card-meta { color: var(--tm-muted); font-size: 0.8rem; line-height: 1.5; }

.tm-card-overdue { border-left: 3px solid #dc4c4c; }

.tm-bar {
    height: 5px;
    border-radius: 999px;
    background: var(--tm-border);
    margin-top: 0.5rem;
    overflow: hidden;
}

.tm-bar span { display: block; height: 100%; border-radius: 999px; background: var(--tm-accent); }

.tm-kanban-col {
    font-size: 0.92rem;
    font-weight: 600;
    color: var(--tm-text);
    padding: 0.4rem 0;
    margin-bottom: 0.4rem;
    border-bottom: 1px solid var(--tm-border);
}

.tm-chip {
    display: inline-block;
    padding: 0.15rem 0.55rem;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 500;
    margin-right: 0.25rem;
    margin-bottom: 0.25rem;
    background: var(--tm-chip-bg);
    color: var(--tm-chip-text);
}

.tm-high { background: var(--tm-high-bg); color: var(--tm-high-text); }
.tm-medium { background: var(--tm-medium-bg); color: var(--tm-medium-text); }
.tm-low { background: var(--tm-low-bg); color: var(--tm-low-text); }
.tm-pending { background: var(--tm-pending-bg); color: var(--tm-pending-text); }
.tm-progress { background: var(--tm-progress-bg); color: var(--tm-progress-text); }
.tm-completed { background: var(--tm-completed-bg); color: var(--tm-completed-text); }
.tm-archived { background: var(--tm-archived-bg); color: var(--tm-archived-text); }
"""


def resolve_theme_name(theme_name) -> str:
    """Map legacy theme names onto the current set, defaulting to the first."""
    resolved = LEGACY_THEME_MAP.get(theme_name, theme_name)
    return resolved if resolved in THEME_OPTIONS else THEME_OPTIONS[0]


def build_css(theme_name) -> str:
    """Full stylesheet for a theme."""
    palette = PALETTES[resolve_theme_name(theme_name)]
    chips = _DARK_CHIPS if palette["is_dark"] else _LIGHT_CHIPS

    variables = [
        f"--tm-accent: {palette['accent']};",
        f"--tm-bg: {palette['bg']};",
        f"--tm-text: {palette['text']};",
        f"--tm-muted: {palette['muted']};",
        f"--tm-card: {palette['card']};",
        f"--tm-sidebar: {palette['sidebar']};",
        f"--tm-border: {palette['border']};",
        f"--tm-btn-text: {palette['btn_text']};",
        f"--tm-chip-bg: {chips['chip_bg']};",
        f"--tm-chip-text: {chips['chip_text']};",
    ]
    for name in ("high", "medium", "low", "pending", "progress", "completed", "archived"):
        background, text_color = chips[name]
        variables.append(f"--tm-{name}-bg: {background};")
        variables.append(f"--tm-{name}-text: {text_color};")

    root_block = ":root {\n    " + "\n    ".join(variables) + "\n}\n"
    return root_block + _STATIC_CSS


def inject_styles(theme_name) -> None:
    """Push the stylesheet for the selected theme into the page."""
    st.markdown(f"<style>{build_css(theme_name)}</style>", unsafe_allow_html=True)
