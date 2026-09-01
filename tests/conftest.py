"""Shared pytest fixtures.

By default each test gets its own throwaway SQLite file via the environment
variables that ``taskflow.config`` reads. Setting ``DATABASE_URL`` (e.g. to run
the suite against Postgres) points every test at the same server instead, so
tables are explicitly emptied between tests rather than relying on a fresh
file - that keeps both backends equally isolated.
"""

from __future__ import annotations

import os

import pytest

from taskflow import db, security
from taskflow.tasks import create_task
from taskflow.users import create_user, get_all_users

# Deletion order respects foreign keys (children before parents).
_TABLES_IN_DELETE_ORDER = (
    "task_attachments",
    "task_comments",
    "subtasks",
    "filter_presets",
    "activity_log",
    "tasks",
    "users",
)


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    """Point the app at an empty database for the duration of a test."""
    monkeypatch.setenv("TASKFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    if not os.environ.get("DATABASE_URL"):
        monkeypatch.setenv("TASKFLOW_DB_PATH", str(tmp_path / "taskflow.db"))
    db.reset_initialisation_state()
    security.reset_login_throttle()
    db.init_db()
    for table in _TABLES_IN_DELETE_ORDER:
        db.execute(f"DELETE FROM {table}")
    yield tmp_path
    db.reset_initialisation_state()


@pytest.fixture
def admin():
    """The first registered account.

    Named ``admin`` for historical reasons and because many tests read more
    naturally with a named "owner" account, but it has no special privileges -
    every account in taskflow has the same permissions.
    """
    create_user("Admin User", "admin@example.com", "admin", "password123")
    return _user_named("admin")


@pytest.fixture
def member(admin):
    """A second, non-privileged account."""
    create_user("Member User", "member@example.com", "member", "password123")
    return _user_named("member")


@pytest.fixture
def other_member(admin):
    """A third account, used to prove permission boundaries."""
    create_user("Other User", "other@example.com", "other", "password123")
    return _user_named("other")


def _user_named(username):
    return next(user for user in get_all_users() if user["username"] == username)


@pytest.fixture
def make_task(admin):
    """Factory creating a task and returning its full row."""

    def _make(
        title="Sample task",
        creator=None,
        assignee=None,
        due_date="2030-01-01",
        priority="Medium",
        status="Pending",
        progress=0,
        tags="",
        recurrence="None",
        category="Other",
    ):
        from taskflow.tasks import get_tasks

        creator = creator or admin
        assignee = assignee or creator
        success, message = create_task(
            title,
            "Description",
            category,
            creator["id"],
            assignee["id"],
            due_date,
            priority,
            status,
            progress,
            tags,
            recurrence,
        )
        assert success, message
        return next(task for task in get_tasks() if task["title"] == title)

    return _make


class FakeUpload:
    """Minimal stand-in for Streamlit's ``UploadedFile``."""

    def __init__(self, name: str, data: bytes = b"hello"):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data
