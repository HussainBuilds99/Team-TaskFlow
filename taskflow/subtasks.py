"""Per-task checklists."""

from __future__ import annotations

from . import db
from .config import MAX_SUBTASK_LENGTH
from .permissions import can_edit_task
from .utils import truncate


def create_subtask(task_id, title, actor, task=None) -> tuple[bool, str]:
    """Add a checklist item to a task."""
    title = truncate(title, MAX_SUBTASK_LENGTH)
    if not title:
        return False, "Subtask title cannot be empty."
    if task is not None and not can_edit_task(task, actor):
        return False, "You do not have permission to change this checklist."
    db.execute("INSERT INTO subtasks (task_id, title, done) VALUES (?, ?, 0)", (task_id, title))
    return True, "Subtask added."


def get_subtasks(task_id) -> list[dict]:
    """Checklist items for a task, in creation order."""
    return db.fetch_all(
        "SELECT id, task_id, title, done FROM subtasks WHERE task_id = ? ORDER BY id ASC",
        (task_id,),
    )


def get_subtasks_for_tasks(task_ids) -> dict[int, list[dict]]:
    """Checklist items for many tasks in a single query.

    Rendering the task list used to issue one query per task per section; this
    keeps a board of 100 tasks to a handful of round trips.
    """
    task_ids = [int(task_id) for task_id in (task_ids or [])]
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    rows = db.fetch_all(
        f"""
        SELECT id, task_id, title, done
        FROM subtasks
        WHERE task_id IN ({placeholders})
        ORDER BY task_id ASC, id ASC
        """,
        task_ids,
    )
    grouped: dict[int, list[dict]] = {task_id: [] for task_id in task_ids}
    for row in rows:
        grouped[row["task_id"]].append(row)
    return grouped


def set_subtask_done(subtask_id, done, actor, task=None) -> tuple[bool, str]:
    """Tick or untick a checklist item."""
    if task is not None and not can_edit_task(task, actor):
        return False, "You do not have permission to change this checklist."
    db.execute("UPDATE subtasks SET done = ? WHERE id = ?", (1 if done else 0, subtask_id))
    return True, "Checklist updated."


def delete_subtask(subtask_id, actor, task=None) -> tuple[bool, str]:
    """Remove a checklist item."""
    if task is not None and not can_edit_task(task, actor):
        return False, "You do not have permission to change this checklist."
    db.execute("DELETE FROM subtasks WHERE id = ?", (subtask_id,))
    return True, "Subtask removed."


def subtask_progress(subtasks) -> int | None:
    """Completion percentage of a checklist, or ``None`` when it is empty."""
    if not subtasks:
        return None
    done = sum(1 for subtask in subtasks if subtask["done"])
    return round(done / len(subtasks) * 100)


def get_subtask_progress(task_id) -> int | None:
    """Completion percentage of a single task's checklist."""
    return subtask_progress(get_subtasks(task_id))
