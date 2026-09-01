"""The signed-in workspace: sidebar filters, KPI strip and tabs."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from ..analytics import TaskFilters, filter_tasks, productivity_summary, sort_tasks
from ..config import (
    CATEGORY_OPTIONS,
    PRIORITY_OPTIONS,
    SORT_OPTIONS,
    STATUS_OPTIONS,
    THEME_OPTIONS,
)
from ..tasks import get_tasks
from ..users import get_all_users, refresh_session_user
from ..utils import escape_html
from .common import render_flashes, render_kpis
from .forms import show_create_task_form
from .panels import (
    PENDING_FILTERS_KEY,
    show_activity_tab,
    show_analytics_tab,
    show_calendar_tab,
    show_kanban_tab,
    show_operations_tab,
    show_planner_tab,
    show_profile_tab,
    show_report_tab,
)
from .task_list import show_task_list
from .theme import inject_styles, resolve_theme_name

DEFAULT_WINDOW_BACK_DAYS = 30
DEFAULT_WINDOW_FORWARD_DAYS = 365


def _render_hero(current_user) -> None:
    st.markdown(
        f"""
        <div class="tm-hero">
            <p class="tm-welcome">Welcome back, <strong>{escape_html(current_user['full_name'])}</strong></p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _sidebar_filters(users) -> tuple[TaskFilters, str]:
    """Render the sidebar and return the chosen filters plus the sort key."""
    st.sidebar.selectbox("Visual Theme", THEME_OPTIONS, key="ui_theme")
    st.sidebar.header("Filters")

    assignee_options = ["All"] + [user["full_name"] for user in users]

    # A preset applied from the Operations tab cannot write to widget-backed
    # state in the same run, so it is parked here and applied on the next one -
    # before any of these widgets exist.
    pending = st.session_state.pop(PENDING_FILTERS_KEY, None)
    if pending:
        st.session_state.update(pending)

    defaults = {
        "filter_search_text": "",
        "filter_tag_filter": "",
        "filter_selected_statuses": list(STATUS_OPTIONS),
        "filter_selected_priorities": list(PRIORITY_OPTIONS),
        "filter_selected_categories": list(CATEGORY_OPTIONS),
        "filter_assigned_filter": "All",
        "filter_mine_only": False,
        "filter_overdue_only": False,
        "filter_include_archived": False,
        "filter_sort_key": SORT_OPTIONS[0],
        "filter_start_date": date.today() - timedelta(days=DEFAULT_WINDOW_BACK_DAYS),
        "filter_end_date": date.today() + timedelta(days=DEFAULT_WINDOW_FORWARD_DAYS),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    # A saved preset or a deleted teammate can leave a value that is no longer
    # offered; reset it before the widget is created so Streamlit does not raise.
    if st.session_state["filter_assigned_filter"] not in assignee_options:
        st.session_state["filter_assigned_filter"] = "All"

    st.sidebar.text_input("Search title, description or tags", key="filter_search_text")
    st.sidebar.text_input(
        "Filter by tag", key="filter_tag_filter", placeholder="urgent,design"
    )
    st.sidebar.multiselect("Status", STATUS_OPTIONS, key="filter_selected_statuses")
    st.sidebar.multiselect("Priority", PRIORITY_OPTIONS, key="filter_selected_priorities")
    st.sidebar.multiselect("Category", CATEGORY_OPTIONS, key="filter_selected_categories")
    st.sidebar.selectbox("Assigned User", assignee_options, key="filter_assigned_filter")
    st.sidebar.selectbox("Sort Tasks By", SORT_OPTIONS, key="filter_sort_key")
    st.sidebar.checkbox("Only my tasks", key="filter_mine_only")
    st.sidebar.checkbox("Only overdue tasks", key="filter_overdue_only")
    st.sidebar.checkbox("Include archived tasks", key="filter_include_archived")
    st.sidebar.date_input("Start Due Date", key="filter_start_date")
    st.sidebar.date_input("End Due Date", key="filter_end_date")

    if st.sidebar.button("Reset filters", width="stretch"):
        for key in defaults:
            st.session_state.pop(key, None)
        st.rerun()

    filters = TaskFilters(
        search_text=st.session_state["filter_search_text"],
        tag_filter=st.session_state["filter_tag_filter"],
        statuses=st.session_state["filter_selected_statuses"],
        priorities=st.session_state["filter_selected_priorities"],
        categories=st.session_state["filter_selected_categories"],
        assignee=st.session_state["filter_assigned_filter"],
        mine_only=st.session_state["filter_mine_only"],
        overdue_only=st.session_state["filter_overdue_only"],
        include_archived=st.session_state["filter_include_archived"],
        start_date=st.session_state["filter_start_date"],
        end_date=st.session_state["filter_end_date"],
    )
    return filters, st.session_state["filter_sort_key"]


def _show_alerts(tasks) -> None:
    summary = productivity_summary(tasks)
    if summary["overdue"]:
        st.warning(f"{summary['overdue']} task(s) are overdue and need attention.")
    if summary["due_today"]:
        st.info(f"{summary['due_today']} task(s) are due today.")
    if summary["due_soon"]:
        st.info(f"{summary['due_soon']} task(s) are due within the next 2 days.")


def show_dashboard() -> None:
    """Render the whole authenticated experience."""
    # Read the account back rather than trusting the copy captured at login, in
    # case the profile was edited from another tab.
    current_user = refresh_session_user(st.session_state.user)
    if not current_user:
        st.session_state.user = None
        st.rerun()
    st.session_state.user = current_user

    st.session_state.setdefault("ui_theme", THEME_OPTIONS[0])
    st.session_state.ui_theme = resolve_theme_name(st.session_state.ui_theme)

    tasks = get_tasks()
    users = get_all_users()
    filters, sort_key = _sidebar_filters(users)
    inject_styles(st.session_state.ui_theme)

    _render_hero(current_user)
    render_flashes()

    _, logout_column = st.columns([5, 1])
    with logout_column:
        if st.button("Logout", width="stretch"):
            for key in [key for key in st.session_state if key != "ui_theme"]:
                del st.session_state[key]
            st.rerun()

    if filters.start_date and filters.end_date and filters.start_date > filters.end_date:
        st.error("The start due date cannot be after the end due date.")
        return

    filtered_tasks = sort_tasks(filter_tasks(tasks, current_user, filters), sort_key)
    summary = productivity_summary(filtered_tasks)
    _show_alerts(filtered_tasks)
    render_kpis(summary)
    st.caption(
        f"Completion rate {summary['completion_rate']}% across "
        f"{summary['total']} task(s) matching your filters."
    )

    tabs = st.tabs(
        [
            "Task Dashboard",
            "Create Task",
            "Kanban",
            "Analytics",
            "Planner",
            "Calendar",
            "Operations",
            "Report & Activity",
            "Profile",
        ]
    )

    with tabs[0]:
        show_task_list(current_user, filtered_tasks)
    with tabs[1]:
        show_create_task_form(current_user)
    with tabs[2]:
        show_kanban_tab(filtered_tasks)
    with tabs[3]:
        show_analytics_tab(filtered_tasks, users)
    with tabs[4]:
        show_planner_tab(filtered_tasks, users)
    with tabs[5]:
        show_calendar_tab(filtered_tasks)
    with tabs[6]:
        show_operations_tab(current_user, users, filtered_tasks, tasks)
    with tabs[7]:
        show_report_tab(filtered_tasks, users)
        show_activity_tab()
    with tabs[8]:
        show_profile_tab(current_user)
