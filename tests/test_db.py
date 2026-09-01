import pytest
from sqlalchemy.exc import IntegrityError

from taskflow import db


def test_init_db_is_idempotent():
    db.init_db()
    db.init_db()
    names = db.list_tables()
    assert {"users", "tasks", "subtasks", "task_comments", "task_attachments", "activity_log"} <= names


def test_foreign_keys_are_enforced():
    with pytest.raises(IntegrityError):
        db.execute(
            """
            INSERT INTO tasks (title, category, creator_id, assignee_id, due_date, priority, status)
            VALUES ('x', 'Other', 999, 999, '2030-01-01', 'High', 'Pending')
            """
        )


def test_execute_returns_affected_row_count(admin):
    changed = db.execute("UPDATE users SET full_name = ? WHERE id = ?", ("New Name", admin["id"]))
    assert changed == 1


def test_execute_returning_id_matches_inserted_row():
    new_id = db.execute_returning_id(
        "INSERT INTO users (full_name, email, username, password_hash) VALUES (?, ?, ?, ?)",
        ("Someone", "someone@example.com", "someone", "hash"),
    )
    row = db.fetch_one("SELECT username FROM users WHERE id = ?", (new_id,))
    assert row["username"] == "someone"


def test_username_lookup_is_case_insensitive_at_the_db_level(admin):
    row = db.fetch_one("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", ("ADMIN",))
    assert row["id"] == admin["id"]
