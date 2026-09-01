"""Sign-in and registration screen."""

from __future__ import annotations

import streamlit as st

from ..config import APP_NAME, APP_TAGLINE, MIN_PASSWORD_LENGTH, THEME_OPTIONS
from ..users import authenticate, create_user
from ..utils import escape_html
from .common import flash, render_flashes
from .theme import inject_styles, resolve_theme_name


def _header() -> None:
    st.markdown(
        f"""
        <div class="tm-auth-shell">
            <h1>{escape_html(APP_NAME)}</h1>
            <p class="tm-auth-sub">{escape_html(APP_TAGLINE)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _login_form() -> None:
    st.subheader("Login to your account")
    with st.form("login_form"):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Login", width="stretch")

    if submitted:
        user, message = authenticate(username, password)
        if user:
            st.session_state.user = user
            flash(f"Welcome back, {user['full_name']}.", "success")
            st.rerun()
        else:
            st.error(message)


def _register_form() -> None:
    st.subheader("Create a new account")
    with st.form("register_form"):
        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        username = st.text_input("Username", help="3-30 characters: letters, numbers, _, . or -")
        password = st.text_input(
            "Password",
            type="password",
            autocomplete="new-password",
            help=f"At least {MIN_PASSWORD_LENGTH} characters.",
        )
        confirm_password = st.text_input(
            "Confirm Password", type="password", autocomplete="new-password"
        )
        submitted = st.form_submit_button("Register", width="stretch")

    if submitted:
        if password != confirm_password:
            st.error("The two passwords do not match.")
            return
        success, message = create_user(full_name, email, username, password)
        if success:
            st.success(message)
        else:
            st.error(message)


def show_auth_page() -> None:
    """Render the whole unauthenticated view."""
    st.session_state.setdefault("ui_theme", THEME_OPTIONS[0])
    st.session_state.ui_theme = resolve_theme_name(st.session_state.ui_theme)
    inject_styles(st.session_state.ui_theme)

    _, center_column, _ = st.columns([1, 1.4, 1])
    with center_column:
        st.selectbox("Visual Theme", THEME_OPTIONS, key="ui_theme")
        render_flashes()
        _header()

        login_tab, register_tab = st.tabs(["Login", "Register"])
        with login_tab:
            _login_form()
        with register_tab:
            _register_form()
