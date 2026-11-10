"""The signed-in workspace: account and filters in the sidebar, counters and five tabs."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from ..analytics import TaskFilters, filter_tasks, productivity_summary, sort_tasks
from ..config import CATEGORY_OPTIONS, PRIORITY_OPTIONS, SORT_OPTIONS, STATUS_OPTIONS
from ..users import refresh_session_user
from ..utils import escape_html, is_overdue, try_parse_due_date
from .common import render_flashes
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
)
from .style import inject_styles
from .task_list import show_task_list
from .widgets import load_tasks, load_users, md_escape, render_kpis

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


#__PART2__
