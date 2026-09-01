"""File attachments stored on disk with metadata in SQLite."""

from __future__ import annotations

import re
import secrets
from pathlib import Path

from . import config, db
from .activity import log_activity
from .config import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_SIZE_BYTES,
    MAX_ATTACHMENT_SIZE_MB,
)
from .permissions import can_edit_task, can_manage_attachment

_UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]+")


def safe_display_name(raw_name) -> str:
    """Reduce an uploaded filename to a harmless, printable basename."""
    base = Path(str(raw_name or "")).name
    cleaned = _UNSAFE_CHARACTERS.sub("_", base).strip("._")
    return cleaned[:120] or "attachment"


def validate_upload(uploaded_file) -> tuple[bool, str]:
    """Check an upload's extension and size before anything touches the disk."""
    if uploaded_file is None:
        return False, "No file selected."

    name = safe_display_name(getattr(uploaded_file, "name", ""))
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))
        return False, f"File type {extension or '(none)'} is not allowed. Allowed: {allowed}."

    data = uploaded_file.getvalue()
    if not data:
        return False, "That file is empty."
    if len(data) > MAX_ATTACHMENT_SIZE_BYTES:
        size_mb = len(data) / (1024 * 1024)
        return False, f"File is too large ({size_mb:.2f} MB). Max allowed is {MAX_ATTACHMENT_SIZE_MB} MB."
    return True, "ok"


def _task_dir(task_id) -> Path:
    return config.upload_dir() / f"task_{int(task_id)}"


def save_attachment(task_id, user_id, uploaded_file, task=None, actor=None) -> tuple[bool, str]:
    """Store an upload for a task and record it in the database."""
    if task is not None and actor is not None and not can_edit_task(task, actor):
        return False, "You do not have permission to attach files to this task."

    valid, message = validate_upload(uploaded_file)
    if not valid:
        return False, message

    display_name = safe_display_name(uploaded_file.name)
    # Two people uploading "notes.pdf" to the same task must not overwrite each
    # other, so the on-disk name gets a random prefix while the display name is
    # kept for downloads.
    stored_name = f"{secrets.token_hex(8)}_{display_name}"
    directory = _task_dir(task_id)
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / stored_name
    file_path.write_bytes(uploaded_file.getvalue())

    db.execute(
        "INSERT INTO task_attachments (task_id, user_id, file_name, file_path) VALUES (?, ?, ?, ?)",
        (task_id, user_id, display_name, str(file_path)),
    )
    log_activity(user_id, "Attachment Uploaded", f"Uploaded '{display_name}' to task #{task_id}")
    return True, "Attachment uploaded successfully."


def get_attachments(task_id) -> list[dict]:
    """Attachments for a task, newest first."""
    return db.fetch_all(
        """
        SELECT task_attachments.id,
               task_attachments.task_id,
               task_attachments.user_id,
               task_attachments.file_name,
               task_attachments.file_path,
               task_attachments.uploaded_at,
               users.full_name AS user_name
        FROM task_attachments
        LEFT JOIN users ON users.id = task_attachments.user_id
        WHERE task_attachments.task_id = ?
        ORDER BY task_attachments.id DESC
        """,
        (task_id,),
    )


def get_attachments_for_tasks(task_ids) -> dict[int, list[dict]]:
    """Attachment metadata for many tasks in one query (no file contents)."""
    task_ids = [int(task_id) for task_id in (task_ids or [])]
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    rows = db.fetch_all(
        f"""
        SELECT task_attachments.id,
               task_attachments.task_id,
               task_attachments.user_id,
               task_attachments.file_name,
               task_attachments.file_path,
               task_attachments.uploaded_at,
               users.full_name AS user_name
        FROM task_attachments
        LEFT JOIN users ON users.id = task_attachments.user_id
        WHERE task_attachments.task_id IN ({placeholders})
        ORDER BY task_attachments.task_id ASC, task_attachments.id DESC
        """,
        task_ids,
    )
    grouped: dict[int, list[dict]] = {task_id: [] for task_id in task_ids}
    for row in rows:
        grouped[row["task_id"]].append(row)
    return grouped


def count_attachments(task_ids) -> dict[int, int]:
    """Attachment totals for many tasks in one query."""
    task_ids = [int(task_id) for task_id in (task_ids or [])]
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    rows = db.fetch_all(
        f"""
        SELECT task_id, COUNT(*) AS total
        FROM task_attachments
        WHERE task_id IN ({placeholders})
        GROUP BY task_id
        """,
        task_ids,
    )
    counts = {task_id: 0 for task_id in task_ids}
    counts.update({row["task_id"]: row["total"] for row in rows})
    return counts


def _resolved_inside_uploads(file_path) -> Path | None:
    """Resolve a stored path, refusing anything outside the upload directory."""
    try:
        root = config.upload_dir().resolve()
        candidate = Path(file_path).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError):
        return None
    return candidate


def read_attachment(attachment) -> bytes | None:
    """Read an attachment's bytes, or ``None`` when the file is gone."""
    candidate = _resolved_inside_uploads(attachment.get("file_path"))
    if not candidate or not candidate.is_file():
        return None
    return candidate.read_bytes()


def delete_attachment(attachment_id, actor, task=None) -> tuple[bool, str]:
    """Delete a single attachment row and its file."""
    attachment = db.fetch_one(
        "SELECT id, task_id, user_id, file_name, file_path FROM task_attachments WHERE id = ?",
        (attachment_id,),
    )
    if not attachment:
        return False, "That attachment no longer exists."
    if not can_manage_attachment(attachment, task, actor):
        return False, "You do not have permission to delete this attachment."

    db.execute("DELETE FROM task_attachments WHERE id = ?", (attachment_id,))
    candidate = _resolved_inside_uploads(attachment["file_path"])
    if candidate and candidate.is_file():
        candidate.unlink(missing_ok=True)
    log_activity(
        actor["id"],
        "Attachment Deleted",
        f"Deleted '{attachment['file_name']}' from task #{attachment['task_id']}",
    )
    return True, "Attachment deleted successfully."


def remove_files_for_task(task_id) -> None:
    """Delete every attachment file belonging to a task (rows cascade)."""
    for attachment in get_attachments(task_id):
        candidate = _resolved_inside_uploads(attachment["file_path"])
        if candidate and candidate.is_file():
            candidate.unlink(missing_ok=True)
    directory = _task_dir(task_id)
    try:
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    except OSError:
        pass
