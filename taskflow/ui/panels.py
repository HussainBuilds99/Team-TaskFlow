"""Secondary dashboard tabs: kanban, planner, operations and reports."""

from __future__ import annotations

import streamlit as st

from ..activity import get_activity_logs
from ..analytics import (
    build_calendar_rows,
    build_team_summary,
    build_workload_rows,
    count_by,
    productivity_summary,
    tag_cloud,
    visible_tasks_for,
)
from ..config import MAX_NAME_LENGTH, PRIORITY_OPTIONS, STATUS_OPTIONS
from ..demo import seed_demo_data
from ..presets import delete_filter_preset, get_filter_presets, save_filter_preset
from ..tasks import bulk_update_tasks, import_tasks_from_csv
from ..users import update_profile
from ..utils import escape_html, is_overdue
from .common import dataframe, report

# Filter values applied from a preset are parked here and picked up by the
# sidebar on the next run: Streamlit forbids writing to a widget's state key
# after that widget has already been created in the current run.
PENDING_FILTERS_KEY = "_pending_filters"

FILTER_STATE_KEYS = (
    "filter_search_text",
    "filter_tag_filter",
    "filter_selected_statuses",
    "filter_selected_priorities",
    "filter_selected_categories",
    "filter_assigned_filter",
    "filter_mine_only",
    "filter_overdue_only",
    "filter_include_archived",
)


# --- Kanban ----------------------------------------------------------------

def show_kanban_tab(tasks) -> None:
    """Three status columns of cards."""
    st.subheader("Kanban View")
    active = [task for task in tasks if not task.get("archived", 0)]
    if not active:
        st.info("No active tasks to show on the board.")
        return

    columns = st.columns(len(STATUS_OPTIONS))
    for index, status_name in enumerate(STATUS_OPTIONS):
        column_tasks = [task for task in active if task["status"] == status_name]
        with columns[index]:
            st.markdown(
                f'<div class="tm-kanban-col">{escape_html(status_name)} '
                f'<span style="color:var(--tm-muted);font-weight:500;">'
                f"({len(column_tasks)})</span></div>",
                unsafe_allow_html=True,
            )
            if not column_tasks:
                st.caption("Nothing here yet.")
            for task in column_tasks:
                progress = int(task.get("progress") or 0)
                card_class = "tm-card tm-card-overdue" if is_overdue(task) else "tm-card"
                st.markdown(
                    f"""
                    <div class="{card_class}">
                        <strong>#{escape_html(task['id'])} · {escape_html(task['title'])}</strong>
                        <div class="tm-card-meta">
                            {escape_html(task['assignee_name'])} · Due {escape_html(task['due_date'])}<br>
                            {escape_html(task['priority'])} priority · {progress}%
                        </div>
                        <div class="tm-bar"><span style="width:{progress}%"></span></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# --- Planner ---------------------------------------------------------------

def show_planner_tab(tasks, users) -> None:
    """Workload distribution and the recurring-task roster."""
    st.subheader("Planner")
    if not tasks:
        st.info("No tasks to plan yet.")
        return

    st.markdown("#### Workload by Assignee")
    dataframe(build_workload_rows(tasks, users))

    st.markdown("#### Recurring Tasks")
    recurring = [
        task
        for task in tasks
        if task.get("recurrence", "None") != "None" and not task.get("archived", 0)
    ]
    if recurring:
        dataframe(
            [
                {
                    "ID": task["id"],
                    "Title": task["title"],
                    "Recurrence": task["recurrence"],
                    "Due Date": task["due_date"],
                    "Assignee": task["assignee_name"],
                    "Status": task["status"],
                    "Last Spawned": task.get("last_recurrence_at") or "-",
                }
                for task in recurring
            ]
        )
    else:
        st.caption("No recurring tasks set.")

    st.markdown("#### Most Used Tags")
    tags = tag_cloud(tasks)
    if tags:
        dataframe(tags)
    else:
        st.caption("No tags used yet.")


# --- Analytics -------------------------------------------------------------

def show_analytics_tab(tasks, users) -> None:
    """Charts and the team performance table."""
    st.subheader("Productivity Analytics")
    if not tasks:
        st.info("No analytics available for the current filters.")
        return

    chart_column1, chart_column2 = st.columns(2)
    with chart_column1:
        st.write("#### Tasks by Status")
        st.bar_chart(count_by(tasks, "status"))
    with chart_column2:
        st.write("#### Tasks by Priority")
        st.bar_chart(count_by(tasks, "priority"))

    st.write("#### Tasks by Category")
    st.bar_chart(count_by(tasks, "category"))

    st.write("#### Team Performance Summary")
    dataframe(build_team_summary(tasks, users))


# --- Calendar --------------------------------------------------------------

def show_calendar_tab(tasks) -> None:
    """Due dates grouped into a simple agenda."""
    st.subheader("Calendar View")
    rows = build_calendar_rows(tasks)
    if not rows:
        st.info("No due dates available for the current filters.")
        return
    dataframe(rows)


# --- Reports and activity --------------------------------------------------

def show_report_tab(tasks, users) -> None:
    """Summary suited to sharing with a supervisor or teacher."""
    st.subheader("Progress Report")
    summary = productivity_summary(tasks)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Visible tasks", summary["total"])
    metric_columns[1].metric("Completed", summary["completed"])
    metric_columns[2].metric("Overdue", summary["overdue"])
    metric_columns[3].metric("Completion rate", f"{summary['completion_rate']}%")

    st.caption(
        f"Average progress {summary['average_progress']}% · "
        f"{summary['in_progress']} in progress · {summary['pending']} pending · "
        f"{summary['archived']} archived · {len(users)} registered user(s)"
    )
    dataframe(build_team_summary(tasks, users))


def show_activity_tab() -> None:
    """The audit log."""
    st.subheader("Activity Log")
    limit = st.slider("Entries to show", min_value=20, max_value=300, value=80, step=20)
    logs = get_activity_logs(limit)
    if not logs:
        st.info("No activity has been recorded yet.")
        return
    dataframe(
        [
            {
                "Time": log["created_at"],
                "User": log["user_name"] or "System",
                "Action": log["action"],
                "Details": log["details"],
            }
            for log in logs
        ]
    )


# --- Profile ---------------------------------------------------------------

def show_profile_tab(current_user) -> None:
    """Let a user edit their own name, email and password."""
    st.subheader("Profile")
    st.caption(f"Signed in as @{current_user['username']}")

    with st.form("profile_form"):
        full_name = st.text_input(
            "Full Name", value=current_user["full_name"], max_chars=MAX_NAME_LENGTH
        )
        email = st.text_input("Email", value=current_user["email"], max_chars=MAX_NAME_LENGTH)
        st.markdown("**Change password** (leave blank to keep the current one)")
        current_password = st.text_input(
            "Current Password", type="password", autocomplete="current-password"
        )
        new_password = st.text_input(
            "New Password", type="password", autocomplete="new-password"
        )
        confirm_password = st.text_input(
            "Confirm New Password", type="password", autocomplete="new-password"
        )
        submitted = st.form_submit_button("Update Profile", width="stretch")

    if not submitted:
        return
    if new_password and new_password != confirm_password:
        st.error("The two new passwords do not match.")
        return

    success, message = update_profile(
        current_user["id"], full_name, email, current_password, new_password
    )
    if success:
        st.session_state.user["full_name"] = full_name.strip()
        st.session_state.user["email"] = email.strip().lower()
    report((success, message))


# --- Operations ------------------------------------------------------------

def _workspace_tools(current_user, users, tasks) -> None:
    st.write(f"This workspace has **{len(users)} user(s)** and **{len(tasks)} task(s)**.")
    st.caption(
        "Demo data only works on an empty workspace; it adds three teammates and "
        "five sample tasks so the app can be presented straight away."
    )
    if st.button("Add Demo Data", width="stretch"):
        success, message = seed_demo_data(current_user)
        if success:
            report((success, message))
        else:
            st.info(message)

def _bulk_operations(current_user, users, filtered_tasks) -> None:
    editable_tasks = visible_tasks_for(filtered_tasks, current_user)
    if not editable_tasks:
        st.info("You have no tasks you can bulk edit with the current filters.")
        return

    label_by_id = {
        task["id"]: f"#{task['id']} · {task['title'][:48]}" for task in editable_tasks
    }
    selected_ids = st.multiselect(
        "Select tasks",
        list(label_by_id.keys()),
        format_func=lambda task_id: label_by_id[task_id],
        key="bulk_selected_ids",
    )

    column1, column2, column3 = st.columns(3)
    with column1:
        bulk_status = st.selectbox("Set Status", ["No Change", *STATUS_OPTIONS], key="bulk_status")
        bulk_priority = st.selectbox(
            "Set Priority", ["No Change", *PRIORITY_OPTIONS], key="bulk_priority"
        )
    with column2:
        assignee_labels = ["No Change"] + [
            f"{user['full_name']} (@{user['username']})" for user in users
        ]
        assignee_ids = [None] + [user["id"] for user in users]
        selected_assignee = st.selectbox("Set Assignee", assignee_labels, key="bulk_assignee")
        archive_action = st.selectbox(
            "Archive action",
            ["No Change", "Archive selected", "Restore selected"],
            key="bulk_archive_action",
        )
    with column3:
        st.write("")
        if st.button("Apply Bulk Update", width="stretch"):
            archive_value = {
                "Archive selected": True,
                "Restore selected": False,
            }.get(archive_action)
            report(
                bulk_update_tasks(
                    selected_ids,
                    current_user,
                    status=None if bulk_status == "No Change" else bulk_status,
                    priority=None if bulk_priority == "No Change" else bulk_priority,
                    assignee_id=assignee_ids[assignee_labels.index(selected_assignee)],
                    archive=archive_value,
                )
            )


def _csv_import(current_user, users) -> None:
    st.caption(
        "Required columns: Title, Due Date (YYYY-MM-DD). "
        "Optional: Description, Category, Priority, Status, Progress %, Tags, Recurrence. "
        "A CSV exported from the Task Dashboard can be re-imported as is."
    )
    uploaded_csv = st.file_uploader("Upload CSV", type=["csv"], key="bulk_csv_import")
    labels = [f"{user['full_name']} (@{user['username']})" for user in users]
    ids = [user["id"] for user in users]
    default_index = ids.index(current_user["id"]) if current_user["id"] in ids else 0
    selected_label = st.selectbox(
        "Assign imported tasks to", labels, index=default_index, key="bulk_import_assignee"
    )

    if st.button("Import CSV Tasks", width="stretch"):
        if uploaded_csv is None:
            st.error("Please choose a CSV file first.")
            return
        report(
            import_tasks_from_csv(
                uploaded_csv.getvalue(),
                current_user["id"],
                ids[labels.index(selected_label)],
            )
        )


def _filter_presets(current_user) -> None:
    preset_name = st.text_input("Preset name", key="preset_name")
    if st.button("Save Current Filters", key="save_filter_button", width="stretch"):
        payload = {key: st.session_state.get(key) for key in FILTER_STATE_KEYS}
        report(save_filter_preset(current_user["id"], preset_name, payload))

    presets = get_filter_presets(current_user["id"])
    if not presets:
        st.caption("No presets saved yet.")
        return

    names = [preset["name"] for preset in presets]
    selected_name = st.selectbox("Your presets", names, key="selected_preset_name")
    column1, column2 = st.columns(2)
    with column1:
        if st.button("Apply Preset", key="apply_preset", width="stretch"):
            payload = next(
                preset["payload"] for preset in presets if preset["name"] == selected_name
            )
            st.session_state[PENDING_FILTERS_KEY] = {
                key: payload[key]
                for key in FILTER_STATE_KEYS
                if payload.get(key) is not None
            }
            st.rerun()
    with column2:
        if st.button("Delete Preset", key="delete_preset", width="stretch"):
            report(delete_filter_preset(current_user["id"], selected_name))


def show_operations_tab(current_user, users, filtered_tasks, all_tasks) -> None:
    """Bulk edits, CSV import, saved filter presets and workspace tools."""
    st.subheader("Bulk Operations & Import")
    with st.expander("Bulk Update Tasks", expanded=True):
        _bulk_operations(current_user, users, filtered_tasks)
    with st.expander("Import Tasks from CSV"):
        _csv_import(current_user, users)
    with st.expander("Saved Filter Presets"):
        _filter_presets(current_user)
    with st.expander("Workspace Tools"):
        _workspace_tools(current_user, users, all_tasks)
