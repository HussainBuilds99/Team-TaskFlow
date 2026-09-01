"""Append-only audit trail of everything that happens in the workspace."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from . import db


def log_activity(user_id, action: str, details: str) -> None:
    """Record an audit entry.

    Logging must never break the operation it describes, so database errors are
    swallowed rather than propagated to the UI.
    """
    try:
        db.execute(
            "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, action, details),
        )
    except SQLAlchemyError:
        pass


def get_activity_logs(limit: int = 50) -> list[dict]:
    """Most recent audit entries, newest first."""
    limit = max(1, min(1000, int(limit)))
    return db.fetch_all(
        """
        SELECT activity_log.action,
               activity_log.details,
               activity_log.created_at,
               users.full_name AS user_name
        FROM activity_log
        LEFT JOIN users ON users.id = activity_log.user_id
        ORDER BY activity_log.id DESC
        LIMIT ?
        """,
        (limit,),
    )
