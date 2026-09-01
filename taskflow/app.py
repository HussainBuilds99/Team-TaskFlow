"""Application entry point."""

from __future__ import annotations

import os

import streamlit as st

from .config import APP_ICON, APP_NAME
from .db import init_db
from .ui.auth_page import show_auth_page
from .ui.dashboard import show_dashboard


def _load_secrets_into_env() -> None:
    """Pull ``DATABASE_URL`` from Streamlit secrets into the environment.

    Lets a hosted deployment configure Postgres via ``.streamlit/secrets.toml``
    (Streamlit Community Cloud's standard mechanism) without changing how
    :mod:`taskflow.config` reads its configuration - it always looks at
    ``os.environ``. Missing/unavailable secrets are fine; SQLite is the
    fallback either way.
    """
    if os.environ.get("DATABASE_URL"):
        return
    try:
        value = st.secrets["DATABASE_URL"]
    except Exception:
        return
    if value:
        os.environ["DATABASE_URL"] = str(value)


def main() -> None:
    """Configure the page, prepare the database and route to the right view."""
    st.set_page_config(
        page_title=APP_NAME,
        page_icon=APP_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _load_secrets_into_env()
    init_db()

    st.session_state.setdefault("user", None)
    st.session_state.setdefault("editing_task_id", None)

    if st.session_state.user is None:
        show_auth_page()
    else:
        show_dashboard()


if __name__ == "__main__":
    main()
