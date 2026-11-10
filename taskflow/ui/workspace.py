"""The signed-in workspace: account and filters in the sidebar, a header and five tabs."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from ..analytics import TaskFilters, filter_tasks, productivity_summary, sort_tasks
from ..config import CATEGORY_OPTIONS, PRIORITY_OPTIONS, SORT_OPTIONS, STATUS_OPTIONS
from ..users import refresh_session_user
from ..utils import is_overdue, try_parse_due_date
from .common import render_flashes
from .home import render_header, show_home_tab
from .panels import (
    PENDING_FILTERS_KEY,
    show_activity_tab,
    show_analytics_tab,
    show_calendar_tab,
    show_kanban_tab,
    show_operations_tab,
    show_planner_tab,
    show_profile_tab,
)
from .style import inject_styles
from .task_list import show_task_list
from .widgets import load_tasks, load_users, md_escape

DEFAULT_WINDOW_BACK_DAYS = 30
DEFAULT_WINDOW_FORWARD_DAYS = 365


def _default_start_date(tasks) -> date:
    """Start of the default due-date window.

    Normally 30 days back, but stretched to the oldest overdue task so that
    long-neglected work is never hidden by the default filters (it would
    otherwise drop out of the list, the counters and the overdue count).
    """
    start = date.today() - timedelta(days=DEFAULT_WINDOW_BACK_DAYS)
    overdue_dates = [
        due
        for due in (try_parse_due_date(task["due_date"]) for task in tasks if is_overdue(task))
        if due is not None
    ]
    return min([start, *overdue_dates])


def _sidebar_account(current_user) -> None:
    st.sidebar.markdown(
        f"**{md_escape(current_user['full_name'])}**  \n"
        f":gray[@{md_escape(current_user['username'])}]"
    )
    if st.sidebar.button("Log out", width="stretch"):
        for key in list(st.session_state):
            del st.session_state[key]
        st.rerun()
    st.sidebar.caption("Light or dark mode: open the ⋮ menu (top right) → Settings.")
    st.sidebar.divider()


def _sidebar_filters(users, tasks) -> tuple[TaskFilters, str]:
    """Render the filters and return them plus the sort key."""
    st.sidebar.subheader("Filters")

    assignee_options = ["All"] + [user["full_name"] for user in users]

    # A preset applied from the Workspace tab cannot write to widget-backed
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
        "filter_start_date": _default_start_date(tasks),
        "filter_end_date": date.today() + timedelta(days=DEFAULT_WINDOW_FORWARD_DAYS),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    # A saved preset or a deleted teammate can leave a value that is no longer
    # offered; reset it before the widget is created so Streamlit does not raise.
    if st.session_state["filter_assigned_filter"] not in assignee_options:
        st.session_state["filter_assigned_filter"] = "All"

    st.sidebar.text_input(
        "Search", key="filter_search_text", placeholder="Title, description or tags"
    )
    st.sidebar.multiselect("Status", STATUS_OPTIONS, key="filter_selected_statuses")
    st.sidebar.selectbox("Sort by", SORT_OPTIONS, key="filter_sort_key")
    st.sidebar.checkbox("Only my tasks", key="filter_mine_only")
    st.sidebar.checkbox("Only overdue tasks", key="filter_overdue_only")

    with st.sidebar.expander("More filters"):
        st.text_input("Tags", key="filter_tag_filter", placeholder="urgent, design")
        st.multiselect("Priority", PRIORITY_OPTIONS, key="filter_selected_priorities")
        st.multiselect("Category", CATEGORY_OPTIONS, key="filter_selected_categories")
        st.selectbox("Assigned to", assignee_options, key="filter_assigned_filter")
        st.date_input("Due from", key="filter_start_date")
        st.date_input("Due until", key="filter_end_date")
        st.checkbox("Include archived tasks", key="filter_include_archived")

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


def show_dashboard() -> None:
    """Render the whole signed-in experience."""
    # Read the account back rather than trusting the copy captured at login, in
    # case the profile was edited from another tab.
    current_user = refresh_session_user(st.session_state.user)
    if not current_user:
        st.session_state.user = None
        st.rerun()
    st.session_state.user = current_user

    inject_styles()
    tasks = load_tasks()
    users = load_users()

    _sidebar_account(current_user)
    filters, sort_key = _sidebar_filters(users, tasks)

    render_header(current_user, tasks)
    render_flashes()

    if filters.start_date and filters.end_date and filters.start_date > filters.end_date:
        st.error("The 'Due from' date cannot be after the 'Due until' date.")
        return

    filtered_tasks = sort_tasks(filter_tasks(tasks, current_user, filters), sort_key)
    summary = productivity_summary(filtered_tasks)

    home_tab, tasks_tab, board_tab, insights_tab, workspace_tab = st.tabs(
        ["Home", "Tasks", "Board", "Insights", "Workspace"]
    )
    with home_tab:
        show_home_tab(current_user, filtered_tasks, users)
    with tasks_tab:
        show_task_list(current_user, filtered_tasks)
    with board_tab:
        show_kanban_tab(filtered_tasks)
        st.divider()
        show_calendar_tab(filtered_tasks)
    with insights_tab:
        st.caption(
            f"Completion rate {summary['completion_rate']}% · "
            f"average progress {summary['average_progress']}% across "
            f"{summary['total']} task(s) matching your filters."
        )
        show_analytics_tab(filtered_tasks, users)
        st.divider()
        show_planner_tab(filtered_tasks, users)
    with workspace_tab:
        tools_tab, activity_tab, profile_tab = st.tabs(["Bulk tools", "Activity log", "Profile"])
        with tools_tab:
            show_operations_tab(current_user, users, filtered_tasks, tasks)
        with activity_tab:
            show_activity_tab()
        with profile_tab:
            show_profile_tab(current_user)
