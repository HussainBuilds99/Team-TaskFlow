"""Task create and edit forms."""

from __future__ import annotations

from datetime import date

import streamlit as st

from ..config import (
    CATEGORY_OPTIONS,
    MAX_DESCRIPTION_LENGTH,
    MAX_TITLE_LENGTH,
    PRIORITY_OPTIONS,
    RECURRENCE_OPTIONS,
    STATUS_OPTIONS,
)
from ..tasks import create_task, update_task
from ..users import get_all_users
from ..utils import try_parse_due_date
from .common import report


def _safe_index(options, value, default: int = 0) -> int:
    """Index of ``value`` in ``options``, or ``default`` when it is not present.

    Guards against values that are valid in the database but absent from the
    current option list - editing such a task used to raise ``ValueError``.
    """
    try:
        return options.index(value)
    except (ValueError, AttributeError):
        return default


def _assignee_choices(users):
    """Labels and a label -> id map, keeping people with identical names apart."""
    labels = []
    label_to_id = {}
    for user in users:
        label = f"{user['full_name']} (@{user['username']})"
        labels.append(label)
        label_to_id[label] = user["id"]
    return labels, label_to_id


def _label_for_user(labels, label_to_id, user_id, fallback_index: int = 0) -> str:
    for label in labels:
        if label_to_id[label] == user_id:
            return label
    return labels[fallback_index] if labels else ""


def show_create_task_form(current_user) -> None:
    """Form for adding a new task."""
    st.subheader("Create Task")
    users = get_all_users()
    if not users:
        st.info("Please create at least one user account first.")
        return

    labels, label_to_id = _assignee_choices(users)
    default_label = _label_for_user(labels, label_to_id, current_user["id"])

    with st.form("create_task_form", clear_on_submit=True):
        title = st.text_input("Task Title", max_chars=MAX_TITLE_LENGTH)
        description = st.text_area("Task Description", max_chars=MAX_DESCRIPTION_LENGTH)
        tags = st.text_input("Tags (comma separated)", placeholder="backend,urgent,team-a")

        column1, column2, column3 = st.columns(3)
        with column1:
            category = st.selectbox("Category", CATEGORY_OPTIONS)
            assigned_label = st.selectbox(
                "Assign To", labels, index=_safe_index(labels, default_label)
            )
        with column2:
            due_date_value = st.date_input("Due Date", value=date.today())
            priority = st.selectbox("Priority", PRIORITY_OPTIONS, index=1)
        with column3:
            status = st.selectbox("Status", STATUS_OPTIONS, index=0)
            progress = st.slider("Progress %", 0, 100, 0, 5)
            recurrence = st.selectbox("Recurrence", RECURRENCE_OPTIONS, index=0)

        submitted = st.form_submit_button("Add Task", width="stretch")

    if submitted:
        report(
            create_task(
                title,
                description,
                category,
                current_user["id"],
                label_to_id[assigned_label],
                due_date_value.isoformat(),
                priority,
                status,
                progress,
                tags,
                recurrence,
            )
        )


def show_edit_task_form(task, current_user) -> None:
    """Inline form for editing an existing task."""
    users = get_all_users()
    if not users:
        st.info("No users available.")
        return

    labels, label_to_id = _assignee_choices(users)
    current_label = _label_for_user(labels, label_to_id, task["assignee_id"])
    current_due = try_parse_due_date(task["due_date"], date.today())

    st.subheader(f"Edit Task #{task['id']}")
    with st.form(f"edit_form_{task['id']}"):
        title = st.text_input("Task Title", value=task["title"], max_chars=MAX_TITLE_LENGTH)
        description = st.text_area(
            "Task Description",
            value=task["description"] or "",
            max_chars=MAX_DESCRIPTION_LENGTH,
        )
        tags = st.text_input("Tags (comma separated)", value=task.get("tags", "") or "")

        column1, column2, column3 = st.columns(3)
        with column1:
            category = st.selectbox(
                "Category", CATEGORY_OPTIONS, index=_safe_index(CATEGORY_OPTIONS, task["category"])
            )
            assigned_label = st.selectbox(
                "Assign To", labels, index=_safe_index(labels, current_label)
            )
        with column2:
            due_date_value = st.date_input("Due Date", value=current_due)
            priority = st.selectbox(
                "Priority", PRIORITY_OPTIONS, index=_safe_index(PRIORITY_OPTIONS, task["priority"], 1)
            )
        with column3:
            status = st.selectbox(
                "Status", STATUS_OPTIONS, index=_safe_index(STATUS_OPTIONS, task["status"])
            )
            progress = st.slider("Progress %", 0, 100, int(task.get("progress") or 0), 5)
            recurrence = st.selectbox(
                "Recurrence",
                RECURRENCE_OPTIONS,
                index=_safe_index(RECURRENCE_OPTIONS, task.get("recurrence", "None")),
            )

        columns = st.columns(2)
        with columns[0]:
            save_clicked = st.form_submit_button("Save Changes", width="stretch")
        with columns[1]:
            cancel_clicked = st.form_submit_button("Cancel", width="stretch")

    if cancel_clicked:
        st.session_state.editing_task_id = None
        st.rerun()

    if save_clicked:
        success = report(
            update_task(
                task["id"],
                current_user,
                title,
                description,
                category,
                label_to_id[assigned_label],
                due_date_value.isoformat(),
                priority,
                status,
                progress,
                tags,
                recurrence,
            ),
            rerun_on_success=False,
        )
        if success:
            st.session_state.editing_task_id = None
            st.rerun()
