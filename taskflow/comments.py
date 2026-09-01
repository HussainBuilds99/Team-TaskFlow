"""Discussion threads attached to tasks."""

from __future__ import annotations

from . import db
from .activity import log_activity
from .config import MAX_COMMENT_LENGTH
from .utils import truncate


def add_comment(task_id, user_id, comment) -> tuple[bool, str]:
    """Post a comment on a task."""
    comment = truncate(comment, MAX_COMMENT_LENGTH)
    if not comment:
        return False, "Comment cannot be empty."
    if not db.fetch_one("SELECT id FROM tasks WHERE id = ?", (task_id,)):
        return False, "That task no longer exists."
    db.execute(
        "INSERT INTO task_comments (task_id, user_id, comment) VALUES (?, ?, ?)",
        (task_id, user_id, comment),
    )
    log_activity(user_id, "Comment Added", f"Added a comment to task #{task_id}")
    return True, "Comment added successfully."


def get_comments(task_id) -> list[dict]:
    """Comments on a task, newest first."""
    return db.fetch_all(
        """
        SELECT task_comments.id,
               task_comments.user_id,
               task_comments.comment,
               task_comments.created_at,
               users.full_name AS user_name
        FROM task_comments
        JOIN users ON users.id = task_comments.user_id
        WHERE task_comments.task_id = ?
        ORDER BY task_comments.id DESC
        """,
        (task_id,),
    )


def get_comments_for_tasks(task_ids) -> dict[int, list[dict]]:
    """Comments for many tasks in one query, newest first within each task."""
    task_ids = [int(task_id) for task_id in (task_ids or [])]
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    rows = db.fetch_all(
        f"""
        SELECT task_comments.id,
               task_comments.task_id,
               task_comments.user_id,
               task_comments.comment,
               task_comments.created_at,
               users.full_name AS user_name
        FROM task_comments
        JOIN users ON users.id = task_comments.user_id
        WHERE task_comments.task_id IN ({placeholders})
        ORDER BY task_comments.task_id ASC, task_comments.id DESC
        """,
        task_ids,
    )
    grouped: dict[int, list[dict]] = {task_id: [] for task_id in task_ids}
    for row in rows:
        grouped[row["task_id"]].append(row)
    return grouped


def count_comments(task_ids) -> dict[int, int]:
    """Comment totals for many tasks in one query."""
    task_ids = [int(task_id) for task_id in (task_ids or [])]
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    rows = db.fetch_all(
        f"""
        SELECT task_id, COUNT(*) AS total
        FROM task_comments
        WHERE task_id IN ({placeholders})
        GROUP BY task_id
        """,
        task_ids,
    )
    counts = {task_id: 0 for task_id in task_ids}
    counts.update({row["task_id"]: row["total"] for row in rows})
    return counts


def delete_comment(comment_id, actor) -> tuple[bool, str]:
    """Delete a comment. Only its author may remove it."""
    row = db.fetch_one(
        "SELECT id, task_id, user_id FROM task_comments WHERE id = ?", (comment_id,)
    )
    if not row:
        return False, "That comment no longer exists."
    if actor["id"] != row["user_id"]:
        return False, "You can only delete your own comments."
    db.execute("DELETE FROM task_comments WHERE id = ?", (comment_id,))
    log_activity(actor["id"], "Comment Deleted", f"Deleted a comment on task #{row['task_id']}")
    return True, "Comment deleted."
