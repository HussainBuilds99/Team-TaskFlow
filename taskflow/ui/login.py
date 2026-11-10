"""Sign-in screen: a short pitch, the one-click demo, then log in / register."""

from __future__ import annotations

import streamlit as st

from ..config import APP_NAME, APP_TAGLINE, MIN_PASSWORD_LENGTH
from ..demo import start_guest_session
from ..users import authenticate, create_user
from ..utils import escape_html
from .common import flash, render_flashes
from .style import inject_styles

FEATURES = (
    ("Plan together", "Assign tasks, set deadlines and track progress across the team."),
    ("See the big picture", "Kanban board, workload planner and analytics in one place."),
    ("Stay on top of it", "Checklists, comments, file attachments and recurring tasks."),
)


def _hero() -> None:
    features = "".join(
        f'<div class="tm-feature"><b>{escape_html(title)}</b>'
        f"<span>{escape_html(text)}</span></div>"
        for title, text in FEATURES
    )
    st.markdown(
        f'<div class="tm-hero"><h1>{escape_html(APP_NAME)}</h1>'
        f"<p>{escape_html(APP_TAGLINE)}</p></div>"
        f'<div class="tm-features">{features}</div>',
        unsafe_allow_html=True,
    )


def _demo_button() -> None:
    """One click into a ready-made workspace, no registration needed."""
    # The keep-alive workflow looks for a button containing "Try the demo".
    if st.button("Try the demo - no sign-up needed", type="primary", width="stretch"):
        user, message = start_guest_session()
        if user:
            st.session_state.user = user
            flash(f"{message} Register your own account any time.", "success")
            st.rerun()
        else:
            st.error(message)


def _login_form() -> None:
    with st.form("login_form"):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Log in", type="primary", width="stretch")

    if submitted:
        user, message = authenticate(username, password)
        if user:
            st.session_state.user = user
            flash(f"Welcome back, {user['full_name']}.", "success")
            st.rerun()
        else:
            st.error(message)


def _register_form() -> None:
    with st.form("register_form"):
        full_name = st.text_input("Full name")
        email = st.text_input("Email")
        username = st.text_input("Username", help="3-30 characters: letters, numbers, _, . or -")
        password = st.text_input(
            "Password",
            type="password",
            autocomplete="new-password",
            help=f"At least {MIN_PASSWORD_LENGTH} characters.",
        )
        confirm_password = st.text_input(
            "Confirm password", type="password", autocomplete="new-password"
        )
        submitted = st.form_submit_button("Create account", type="primary", width="stretch")

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
    """Render the whole signed-out view."""
    inject_styles()
    _hero()

    _, center_column, _ = st.columns([1, 1.4, 1])
    with center_column:
        render_flashes()
        _demo_button()
        st.caption("Explore a sample workspace instantly, or use your own account below.")

        login_tab, register_tab = st.tabs(["Log in", "Create account"])
        with login_tab:
            _login_form()
        with register_tab:
            _register_form()
