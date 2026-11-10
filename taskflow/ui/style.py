"""Page styling.

Colours come from Streamlit's own theme (``.streamlit/config.toml`` defines a
light and a dark palette and each visitor picks one from the app menu), so the
built-in widgets are never restyled here. The few custom components below use
translucent neutrals and inherit the text colour, which keeps them readable on
either background.
"""

from __future__ import annotations

import streamlit as st

_CSS = """
:root { --tm-muted: #8b93a7; --tm-line: rgba(128, 128, 128, 0.22); --tm-fill: rgba(128, 128, 128, 0.06); }

.block-container { padding-top: 3.5rem; padding-bottom: 3rem; max-width: 1100px; }

/* Sign-in page */
.tm-hero { text-align: center; padding: 2rem 1rem 0.5rem; }
.tm-hero h1 { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 0.5rem; padding: 0; }
.tm-hero p { color: var(--tm-muted); font-size: 1.05rem; margin: 0 auto; max-width: 34rem; }
.tm-features { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.75rem; margin: 1.5rem 0 1.75rem; }
@media (max-width: 700px) { .tm-features { grid-template-columns: 1fr; } }
.tm-feature { border: 1px solid var(--tm-line); border-radius: 12px; padding: 0.9rem 1rem; background: var(--tm-fill); }
.tm-feature b { display: block; margin-bottom: 0.2rem; }
.tm-feature span { color: var(--tm-muted); font-size: 0.88rem; }

/* Workspace header */
.tm-welcome { font-size: 1.6rem; font-weight: 700; margin: 0; }
.tm-sub { color: var(--tm-muted); margin: 0.15rem 0 0; }

/* Counter tiles */
.tm-kpi-wrap { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0.6rem; margin: 1rem 0 1.25rem; }
@media (max-width: 900px) { .tm-kpi-wrap { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 520px) { .tm-kpi-wrap { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.tm-kpi { border: 1px solid var(--tm-line); border-left: 4px solid var(--kpi, #6366f1); border-radius: 10px; padding: 0.7rem 0.85rem; background: var(--tm-fill); }
.tm-kpi .label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--tm-muted); }
.tm-kpi .value { font-size: 1.5rem; font-weight: 700; margin-top: 0.1rem; }

/* Kanban cards */
.tm-kanban-col { font-weight: 600; padding: 0.4rem 0; margin-bottom: 0.5rem; border-bottom: 1px solid var(--tm-line); }
.tm-card { border: 1px solid var(--tm-line); border-radius: 10px; padding: 0.85rem 1rem; margin-bottom: 0.65rem; background: var(--tm-fill); }
.tm-card-overdue { border-left: 4px solid #ef4444; }
.tm-card-meta { color: var(--tm-muted); font-size: 0.82rem; line-height: 1.5; margin-top: 0.2rem; }
.tm-bar { height: 5px; border-radius: 999px; background: var(--tm-line); margin-top: 0.55rem; overflow: hidden; }
.tm-bar span { display: block; height: 100%; border-radius: 999px; background: #6366f1; }
"""


def inject_styles() -> None:
    """Add the custom-component stylesheet to the page."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
