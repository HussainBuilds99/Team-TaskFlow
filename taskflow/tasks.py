"""Task creation, editing, archiving, recurrence and bulk operations."""

from __future__ import annotations

import csv
import io

from . import db
from .activity import log_activity
from .config import (
    CATEGORY_OPTIONS,
    DEFAULT_CATEGORY,
    DEFAULT_PRIORITY,
    DEFAULT_RECURRENCE,
    DEFAULT_STATUS,
    MAX_CSV_ROWS,
    MAX_DESCRIPTION_LENGTH,
    MAX_TITLE_LENGTH,
    MIN_TITLE_LENGTH,
    PRIORITY_OPTIONS,
    RECURRENCE_OPTIONS,
    RECURRING_VALUES,
    STATUS_OPTIONS,
)
from .permissions import can_delete_task, can_edit_task
from .utils import clamp_int, next_due_date, normalize_tags, parse_due_date, truncate

TASK_COLUMNS = """
    tasks.id,
    tasks.title,
    tasks.description,
    tasks.category,
    tasks.creator_id,
    tasks.assignee_id,
    tasks.due_date,
    tasks.priority,
    tasks.status,
    tasks.progress,
    tasks.tags,
    tasks.recurrence,
    tasks.last_recurrence_at,
    tasks.archived,
    tasks.previous_status,
    tasks.created_at,
    tasks.updated_at,
    creator.full_name AS creator_name,
    assignee.full_name AS assignee_name
"""


def _validated_fields(
    title,
    description,
    category,
    assignee_id,
    due_date_value,
    priority,
    status,
    progress,
    tags,
    recurrence,
):
    """Normalise and validate task input, returning ``(error, fields)``."""
    title = truncate(title, MAX_TITLE_LENGTH)
    if not title:
        return "Task title is required.", None
    if len(title) < MIN_TITLE_LENGTH:
        return f"Task title must be at least {MIN_TITLE_LENGTH} characters long.", None
    if category not in CATEGORY_OPTIONS:
        return "Invalid category.", None
    if priority not in PRIORITY_OPTIONS:
        return "Invalid priority.", None
    if status not in STATUS_OPTIONS:
        return "Invalid status.", None
    if recurrence not in RECURRENCE_OPTIONS:
        return "Invalid recurrence.", None

    try:
        due_date = parse_due_date(due_date_value)
    except (ValueError, TypeError):
        return "Due date must be a valid date (YYYY-MM-DD).", None

    if not db.fetch_one("SELECT id FROM users WHERE id = ?", (assignee_id,)):
        return "The selected assignee no longer exists.", None

    progress = clamp_int(progress, 0, 100)
    # A completed task is always at 100%; keeping them in sync avoids reports
    # that show "Completed / 40%".
    if status == "Completed":
        progress = 100

    return None, {
        "title": title,
        "description": truncate(description, MAX_DESCRIPTION_LENGTH),
        "category": category,
        "assignee_id": assignee_id,
        "due_date": due_date.isoformat(),
        "priority": priority,
        "status": status,
        "progress": progress,
        "tags": normalize_tags(tags),
        "recurrence": recurrence,
    }


def create_task(
    title,
    description,
    category,
    creator_id,
    assignee_id,
    due_date_value,
    priority,
    status,
    progress=0,
    tags="",
    recurrence=DEFAULT_RECURRENCE,
) -> tuple[bool, str]:
    """Create a task, returning ``(success, message)``."""
    error, fields = _validated_fields(
        title,
        description,
        category,
        assignee_id,
        due_date_value,
        priority,
        status,
        progress,
        tags,
        recurrence,
    )
    if error:
        return False, error

    db.execute(
        """
        INSERT INTO tasks (
            title, description, category, creator_id, assignee_id, due_date,
            priority, status, progress, tags, recurrence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fields["title"],
            fields["description"],
            fields["category"],
            creator_id,
            fields["assignee_id"],
            fields["due_date"],
            fields["priority"],
            fields["status"],
            fields["progress"],
            fields["tags"],
            fields["recurrence"],
        ),
    )
    log_activity(creator_id, "Task Created", f"Created task '{fields['title']}'")
    return True, "Task created successfully."


def get_tasks() -> list[dict]:
    """Every task with creator and assignee names attached."""
    return db.fetch_all(
        f"""
        SELECT {TASK_COLUMNS}
        FROM tasks
        JOIN users AS creator ON creator.id = tasks.creator_id
        JOIN users AS assignee ON assignee.id = tasks.assignee_id
        ORDER BY date(tasks.due_date) ASC, tasks.id DESC
        """
    )


def get_task(task_id) -> dict | None:
    """A single task with creator and assignee names attached."""
    return db.fetch_one(
        f"""
        SELECT {TASK_COLUMNS}
        FROM tasks
        JOIN users AS creator ON creator.id = tasks.creator_id
        JOIN users AS assignee ON assignee.id = tasks.assignee_id
        WHERE tasks.id = ?
        """,
        (task_id,),
    )


def update_task(
    task_id,
    actor,
    title,
    description,
    category,
    assignee_id,
    due_date_value,
    priority,
    status,
    progress=0,
    tags="",
    recurrence=DEFAULT_RECURRENCE,
) -> tuple[bool, str]:
    """Update a task on behalf of ``actor`` (who must be allowed to edit it)."""
    task = get_task(task_id)
    if not task:
        return False, "That task no longer exists."
    if not can_edit_task(task, actor):
        return False, "You do not have permission to edit this task."

    error, fields = _validated_fields(
        title,
        description,
        category,
        assignee_id,
        due_date_value,
        priority,
        status,
        progress,
        tags,
        recurrence,
    )
    if error:
        return False, error

    db.execute(
        """
        UPDATE tasks
        SET title = ?,
            description = ?,
            category = ?,
            assignee_id = ?,
            due_date = ?,
            priority = ?,
            status = ?,
            progress = ?,
            tags = ?,
            recurrence = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            fields["title"],
            fields["description"],
            fields["category"],
            fields["assignee_id"],
            fields["due_date"],
            fields["priority"],
            fields["status"],
            fields["progress"],
            fields["tags"],
            fields["recurrence"],
            task_id,
        ),
    )
    log_activity(actor["id"], "Task Updated", f"Updated task '{fields['title']}'")
    return True, "Task updated successfully."


def set_task_status(task_id, actor, status) -> tuple[bool, str]:
    """Quick status change used by the task list's inline controls."""
    if status not in STATUS_OPTIONS:
        return False, "Invalid status."
    task = get_task(task_id)
    if not task:
        return False, "That task no longer exists."
    if not can_edit_task(task, actor):
        return False, "You do not have permission to edit this task."

    progress = 100 if status == "Completed" else task.get("progress", 0)
    db.execute(
        """
        UPDATE tasks
        SET status = ?, progress = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, progress, task_id),
    )
    log_activity(actor["id"], "Status Changed", f"Task #{task_id} set to {status}")
    return True, f"Task marked as {status}."


def archive_task(task_id, actor) -> tuple[bool, str]:
    """Archive a task, remembering the status to restore later."""
    task = get_task(task_id)
    if not task:
        return False, "That task no longer exists."
    if not can_delete_task(task, actor):
        return False, "Only the task creator can archive this task."
    if task.get("archived", 0):
        return True, "Task is already archived."

    db.execute(
        """
        UPDATE tasks
        SET archived = 1, previous_status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (task["status"], task_id),
    )
    log_activity(actor["id"], "Task Archived", f"Archived task '{task['title']}'")
    return True, "Task archived successfully."


def restore_task(task_id, actor) -> tuple[bool, str]:
    """Restore an archived task to the status it had before archiving."""
    task = get_task(task_id)
    if not task:
        return False, "That task no longer exists."
    if not can_delete_task(task, actor):
        return False, "Only the task creator can restore this task."
    if not task.get("archived", 0):
        return True, "Task is not archived."

    previous = task.get("previous_status")
    if previous not in STATUS_OPTIONS:
        previous = DEFAULT_STATUS
    db.execute(
        """
        UPDATE tasks
        SET archived = 0,
            status = ?,
            previous_status = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (previous, task_id),
    )
    log_activity(actor["id"], "Task Restored", f"Restored task '{task['title']}'")
    return True, "Task restored successfully."


def delete_task(task_id, actor) -> tuple[bool, str]:
    """Permanently delete a task along with its attachment files on disk."""
    from .attachments import remove_files_for_task

    task = get_task(task_id)
    if not task:
        return False, "That task no longer exists."
    if not can_delete_task(task, actor):
        return False, "Only the task creator can delete this task."

    # Rows cascade with the task; the files behind them have to go explicitly or
    # they would linger on disk forever.
    remove_files_for_task(task_id)
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    log_activity(actor["id"], "Task Deleted", f"Deleted task '{task['title']}'")
    return True, "Task deleted successfully."


def create_next_recurring_task(task, actor) -> tuple[bool, str]:
    """Spawn the next cycle of a recurring task."""
    recurrence = task.get("recurrence", DEFAULT_RECURRENCE)
    if recurrence not in RECURRING_VALUES:
        return False, "Task is not recurring."
    if not can_edit_task(task, actor):
        return False, "You do not have permission to extend this task."

    upcoming = next_due_date(task["due_date"], recurrence).isoformat()
    existing = db.fetch_one(
        """
        SELECT id FROM tasks
        WHERE title = ? AND assignee_id = ? AND creator_id = ? AND due_date = ?
              AND archived = 0
        LIMIT 1
        """,
        (task["title"], task["assignee_id"], task["creator_id"], upcoming),
    )
    if existing:
        return False, "Next recurring task already exists."

    success, message = create_task(
        task["title"],
        task.get("description", ""),
        task["category"],
        task["creator_id"],
        task["assignee_id"],
        upcoming,
        task["priority"],
        DEFAULT_STATUS,
        0,
        task.get("tags", ""),
        recurrence,
    )
    if success:
        db.execute(
            "UPDATE tasks SET last_recurrence_at = CURRENT_TIMESTAMP WHERE id = ?",
            (task["id"],),
        )
        log_activity(
            actor["id"],
            "Recurring Task Created",
            f"Created next cycle of task #{task['id']} due {upcoming}",
        )
        return True, f"Next cycle created, due {upcoming}."
    return success, message


def bulk_update_tasks(
    task_ids, actor, status=None, priority=None, assignee_id=None, archive=None
) -> tuple[bool, str]:
    """Apply the same change to several tasks, skipping any the actor cannot edit."""
    task_ids = [int(task_id) for task_id in (task_ids or [])]
    if not task_ids:
        return False, "No tasks selected."
    if status is not None and status not in STATUS_OPTIONS:
        return False, "Invalid status."
    if priority is not None and priority not in PRIORITY_OPTIONS:
        return False, "Invalid priority."
    if assignee_id is not None and not db.fetch_one(
        "SELECT id FROM users WHERE id = ?", (assignee_id,)
    ):
        return False, "The selected assignee no longer exists."

    updates: list[str] = []
    params: list = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
        if status == "Completed":
            updates.append("progress = 100")
    if priority is not None:
        updates.append("priority = ?")
        params.append(priority)
    if assignee_id is not None:
        updates.append("assignee_id = ?")
        params.append(assignee_id)
    if archive is not None:
        updates.append("archived = ?")
        params.append(1 if archive else 0)
        if not archive:
            updates.append("status = COALESCE(previous_status, status)")
            updates.append("previous_status = NULL")
    if not updates:
        return False, "No changes selected."

    allowed: list[int] = []
    skipped = 0
    for task_id in task_ids:
        task = get_task(task_id)
        if not task:
            skipped += 1
            continue
        # Archiving follows the stricter delete permission, everything else the
        # edit permission.
        permitted = (
            can_delete_task(task, actor) if archive is not None else can_edit_task(task, actor)
        )
        if permitted:
            allowed.append(task_id)
        else:
            skipped += 1

    if not allowed:
        return False, "You do not have permission to change the selected tasks."

    # `previous_status` has to be captured before the status column is rewritten.
    if archive:
        placeholders = ",".join("?" for _ in allowed)
        db.execute(
            f"""
            UPDATE tasks
            SET previous_status = status
            WHERE id IN ({placeholders}) AND archived = 0
            """,
            allowed,
        )

    placeholders = ",".join("?" for _ in allowed)
    db.execute(
        f"UPDATE tasks SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP "
        f"WHERE id IN ({placeholders})",
        params + allowed,
    )
    log_activity(actor["id"], "Bulk Update", f"Bulk updated {len(allowed)} task(s)")

    message = f"Updated {len(allowed)} task(s)."
    if skipped:
        message += f" Skipped {skipped} task(s) you cannot change."
    return True, message


CSV_REQUIRED_COLUMNS = ("Title", "Due Date")


def import_tasks_from_csv(file_bytes, creator_id, fallback_assignee_id) -> tuple[bool, str]:
    """Bulk-create tasks from a CSV export produced by this app."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except (UnicodeDecodeError, AttributeError):
        return False, "CSV must be a UTF-8 encoded text file."

    reader = csv.DictReader(io.StringIO(text))
    headers = {(name or "").strip() for name in (reader.fieldnames or [])}
    missing = [column for column in CSV_REQUIRED_COLUMNS if column not in headers]
    if missing:
        return False, f"CSV is missing required column(s): {', '.join(missing)}."

    created = 0
    skipped = 0
    for index, row in enumerate(reader):
        if index >= MAX_CSV_ROWS:
            skipped += 1
            continue

        def cell(name, default=""):
            return (row.get(name) or default).strip()

        category = cell("Category", DEFAULT_CATEGORY) or DEFAULT_CATEGORY
        priority = cell("Priority", DEFAULT_PRIORITY) or DEFAULT_PRIORITY
        status = cell("Status", DEFAULT_STATUS) or DEFAULT_STATUS
        recurrence = cell("Recurrence", DEFAULT_RECURRENCE) or DEFAULT_RECURRENCE

        success, _ = create_task(
            title=cell("Title"),
            description=cell("Description"),
            category=category if category in CATEGORY_OPTIONS else DEFAULT_CATEGORY,
            creator_id=creator_id,
            assignee_id=fallback_assignee_id,
            due_date_value=cell("Due Date"),
            priority=priority if priority in PRIORITY_OPTIONS else DEFAULT_PRIORITY,
            status=status if status in STATUS_OPTIONS else DEFAULT_STATUS,
            progress=clamp_int(cell("Progress %", "0"), 0, 100),
            tags=cell("Tags"),
            recurrence=recurrence if recurrence in RECURRENCE_OPTIONS else DEFAULT_RECURRENCE,
        )
        if success:
            created += 1
        else:
            skipped += 1

    if created:
        log_activity(creator_id, "CSV Import", f"Imported {created} task(s) from CSV")
    return True, f"Imported {created} task(s), skipped {skipped} row(s)."
