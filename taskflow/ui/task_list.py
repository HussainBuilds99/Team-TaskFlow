"""The "Task Dashboard" tab: table, pagination and per-task detail panels."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ..analytics import export_tasks_csv, format_task_table
from ..attachments import (
    delete_attachment,
    get_attachments_for_tasks,
    read_attachment,
    save_attachment,
)
from ..comments import add_comment, delete_comment, get_comments_for_tasks
from ..config import MAX_COMMENT_LENGTH, MAX_SUBTASK_LENGTH
from ..permissions import can_delete_task, can_edit_task, can_manage_attachment
from ..subtasks import (
    create_subtask,
    delete_subtask,
    get_subtasks_for_tasks,
    set_subtask_done,
    subtask_progress,
)
from ..tasks import archive_task, create_next_recurring_task, delete_task, restore_task, set_task_status
from ..utils import escape_html, is_overdue
from .common import confirm_button, dataframe, flash, render_task_chips, report
from .forms import show_edit_task_form

PAGE_SIZE_OPTIONS = [5, 10, 25, 50]
# Files above this size are fetched from disk only when the user asks, so the
# page does not re-read large uploads on every interaction.
INLINE_DOWNLOAD_LIMIT_BYTES = 2 * 1024 * 1024


def _paginate(tasks, key_prefix: str):
    """Render the pagination controls and return the current page of tasks."""
    control_columns = st.columns([1, 1, 2])
    with control_columns[0]:
        page_size = st.selectbox(
            "Tasks per page", PAGE_SIZE_OPTIONS, index=1, key=f"{key_prefix}_page_size"
        )
    total_pages = max(1, -(-len(tasks) // page_size))
    with control_columns[1]:
        page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key=f"{key_prefix}_page",
        )
    page = min(int(page), total_pages)
    start = (page - 1) * page_size
    window = tasks[start : start + page_size]
    with control_columns[2]:
        st.caption(
            f"Showing {start + 1}-{start + len(window)} of {len(tasks)} task(s) "
            f"· page {page} of {total_pages}"
        )
    return window


def _toggle_subtask(subtask_id, state_key, task, current_user) -> None:
    """``on_change`` handler so the checkbox and the database stay in step."""
    success, message = set_subtask_done(
        subtask_id, st.session_state.get(state_key, False), current_user, task
    )
    if not success:
        # Put the widget back where it was and explain why.
        st.session_state[state_key] = not st.session_state.get(state_key, False)
        flash(message, "error")


def _render_checklist(task, current_user, subtasks) -> None:
    st.markdown("#### Checklist")
    editable = can_edit_task(task, current_user)

    if subtasks:
        percent = subtask_progress(subtasks)
        st.progress(percent / 100, text=f"{percent}% of checklist complete")
        for subtask in subtasks:
            columns = st.columns([5, 1])
            state_key = f"subtask_done_{subtask['id']}"
            with columns[0]:
                st.checkbox(
                    subtask["title"],
                    value=bool(subtask["done"]),
                    key=state_key,
                    disabled=not editable,
                    on_change=_toggle_subtask,
                    args=(subtask["id"], state_key, task, current_user),
                )
            with columns[1]:
                if editable and st.button(
                    "Remove", key=f"del_subtask_{subtask['id']}", width="stretch"
                ):
                    report(delete_subtask(subtask["id"], current_user, task))
    else:
        st.caption("No checklist items yet.")

    if editable:
        with st.form(f"add_subtask_form_{task['id']}", clear_on_submit=True):
            subtask_title = st.text_input("Add checklist item", max_chars=MAX_SUBTASK_LENGTH)
            if st.form_submit_button("Add checklist item", width="stretch"):
                report(create_subtask(task["id"], subtask_title, current_user, task))


def _render_comments(task, current_user, comments) -> None:
    st.markdown(f"#### Comments ({len(comments)})")
    for comment in comments:
        columns = st.columns([6, 1])
        with columns[0]:
            st.markdown(
                f"**{escape_html(comment['user_name'])}** "
                f"<span style='color:var(--tm-muted);font-size:0.8rem;'>"
                f"{escape_html(comment['created_at'])}</span>",
                unsafe_allow_html=True,
            )
            st.write(comment["comment"])
        with columns[1]:
            can_remove = comment["user_id"] == current_user["id"]
            if can_remove and st.button(
                "Delete", key=f"del_comment_{comment['id']}", width="stretch"
            ):
                report(delete_comment(comment["id"], current_user))
    if not comments:
        st.caption("No comments yet.")

    with st.form(f"comment_form_{task['id']}", clear_on_submit=True):
        comment_text = st.text_area("Add Comment", max_chars=MAX_COMMENT_LENGTH)
        if st.form_submit_button("Post Comment", width="stretch"):
            report(add_comment(task["id"], current_user["id"], comment_text))


def _render_attachments(task, current_user, attachments) -> None:
    st.markdown(f"#### Attachments ({len(attachments)})")
    for attachment in attachments:
        columns = st.columns([4, 1])
        data = None
        try:
            candidate = Path(attachment["file_path"])
            size = candidate.stat().st_size if candidate.is_file() else None
        except OSError:
            size = None

        with columns[0]:
            if size is None:
                st.caption(f"{attachment['file_name']} - file is missing from storage.")
            elif size <= INLINE_DOWNLOAD_LIMIT_BYTES:
                data = read_attachment(attachment)
                if data is None:
                    st.caption(f"{attachment['file_name']} - file is missing from storage.")
                else:
                    st.download_button(
                        f"Download {attachment['file_name']}",
                        data=data,
                        file_name=attachment["file_name"],
                        key=f"download_{attachment['id']}",
                        width="stretch",
                    )
            else:
                prepared_key = f"prepared_attachment_{attachment['id']}"
                if st.session_state.get(prepared_key):
                    data = read_attachment(attachment)
                    if data is not None:
                        st.download_button(
                            f"Download {attachment['file_name']} ({size / 1048576:.1f} MB)",
                            data=data,
                            file_name=attachment["file_name"],
                            key=f"download_{attachment['id']}",
                            width="stretch",
                        )
                elif st.button(
                    f"Prepare {attachment['file_name']} ({size / 1048576:.1f} MB)",
                    key=f"prepare_{attachment['id']}",
                    width="stretch",
                ):
                    st.session_state[prepared_key] = True
                    st.rerun()
            st.caption(f"Uploaded by {attachment.get('user_name') or 'Unknown'} · {attachment['uploaded_at']}")

        with columns[1]:
            if can_manage_attachment(attachment, task, current_user) and st.button(
                "Delete", key=f"del_attach_{attachment['id']}", width="stretch"
            ):
                report(delete_attachment(attachment["id"], current_user, task))

    if not attachments:
        st.caption("No attachments yet.")

    if can_edit_task(task, current_user):
        uploaded_file = st.file_uploader(
            "Attach a file", key=f"upload_{task['id']}", label_visibility="collapsed"
        )
        if st.button("Upload Attachment", key=f"upload_btn_{task['id']}", width="stretch"):
            report(
                save_attachment(task["id"], current_user["id"], uploaded_file, task, current_user)
            )


def _render_actions(task, current_user) -> None:
    """Quick actions row: status, edit, archive/restore, delete, next cycle."""
    if not can_edit_task(task, current_user):
        st.caption("You have read-only access to this task.")
        return

    columns = st.columns(4)
    with columns[0]:
        next_status = {
            "Pending": "In Progress",
            "In Progress": "Completed",
            "Completed": "Pending",
        }[task["status"]]
        if not task.get("archived", 0) and st.button(
            f"Mark {next_status}", key=f"status_{task['id']}", width="stretch"
        ):
            report(set_task_status(task["id"], current_user, next_status))
    with columns[1]:
        if st.button("Edit", key=f"edit_{task['id']}", width="stretch"):
            st.session_state.editing_task_id = task["id"]
            st.rerun()
    with columns[2]:
        if can_delete_task(task, current_user):
            if task.get("archived", 0):
                if st.button("Restore", key=f"restore_{task['id']}", width="stretch"):
                    report(restore_task(task["id"], current_user))
            elif st.button("Archive", key=f"archive_{task['id']}", width="stretch"):
                report(archive_task(task["id"], current_user))
    with columns[3]:
        if task.get("recurrence", "None") != "None" and st.button(
            "Create Next Cycle", key=f"next_cycle_{task['id']}", width="stretch"
        ):
            report(create_next_recurring_task(task, current_user))

    if can_delete_task(task, current_user):
        if confirm_button(
            "Delete task",
            key=f"delete_{task['id']}",
            help_text="Permanently removes the task, its checklist, comments and attachments.",
        ):
            report(delete_task(task["id"], current_user))


def _task_header(task) -> str:
    parts = [
        f"#{task['id']} · {task['title']}",
        task["status"],
        task["priority"],
        f"Due {task['due_date']}",
    ]
    if task.get("archived", 0):
        parts.append("Archived")
    if is_overdue(task):
        parts.append("OVERDUE")
    return "  |  ".join(parts)


def show_task_list(current_user, filtered_tasks) -> None:
    """Render the tasks table plus one detail panel per task on the page."""
    st.subheader("Tasks")
    if not filtered_tasks:
        st.info("No tasks match the current filters.")
        return

    st.download_button(
        "Download Filtered Tasks as CSV",
        data=export_tasks_csv(filtered_tasks),
        file_name="task_report.csv",
        mime="text/csv",
    )
    dataframe(format_task_table(filtered_tasks))

    st.markdown("### Manage Tasks")
    page_tasks = _paginate(filtered_tasks, "tasks")
    page_ids = [task["id"] for task in page_tasks]

    # One query each for the whole page instead of three per task.
    subtasks_by_task = get_subtasks_for_tasks(page_ids)
    comments_by_task = get_comments_for_tasks(page_ids)
    attachments_by_task = get_attachments_for_tasks(page_ids)

    for task in page_tasks:
        with st.expander(_task_header(task)):
            render_task_chips(task)
            st.write(f"**Description:** {task['description'] or 'No description provided.'}")

            meta_columns = st.columns(3)
            meta_columns[0].caption(f"Created by {task['creator_name']}")
            meta_columns[1].caption(f"Assigned to {task['assignee_name']}")
            meta_columns[2].caption(f"Last updated {task['updated_at']}")

            subtasks = subtasks_by_task.get(task["id"], [])
            derived = subtask_progress(subtasks)
            if derived is not None and derived != int(task.get("progress") or 0):
                st.caption(f"Checklist progress suggests {derived}% completion.")

            _render_actions(task, current_user)

            if st.session_state.get("editing_task_id") == task["id"]:
                show_edit_task_form(task, current_user)

            _render_checklist(task, current_user, subtasks)
            _render_comments(task, current_user, comments_by_task.get(task["id"], []))
            _render_attachments(task, current_user, attachments_by_task.get(task["id"], []))
