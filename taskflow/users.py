"""User accounts and authentication.

Every account has the same permissions - what a person can do to a task is
decided by whether they created it or are assigned to it (see
:mod:`taskflow.permissions`), not by any notion of role.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from . import db, security
from .activity import log_activity
from .config import MAX_NAME_LENGTH
from .security import (
    clear_failed_logins,
    hash_password,
    lockout_remaining,
    needs_rehash,
    password_problem,
    record_failed_login,
    validate_email,
    validate_username,
    verify_password,
)
from .utils import truncate

_PUBLIC_COLUMNS = "id, full_name, email, username, created_at"


def user_count() -> int:
    """Number of registered accounts."""
    row = db.fetch_one("SELECT COUNT(*) AS count FROM users")
    return row["count"] if row else 0


def get_all_users() -> list[dict]:
    """Every account, ordered by display name."""
    return db.fetch_all(f"SELECT {_PUBLIC_COLUMNS} FROM users ORDER BY LOWER(full_name)")


def get_user(user_id) -> dict | None:
    """Look up a single account by id."""
    return db.fetch_one(f"SELECT {_PUBLIC_COLUMNS} FROM users WHERE id = ?", (user_id,))


def username_taken(username: str) -> bool:
    """True when the username already exists (compared case-insensitively)."""
    row = db.fetch_one(
        "SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),)
    )
    return row is not None


def create_user(full_name, email, username, password, **_ignored) -> tuple[bool, str]:
    """Register a new account.

    Any extra keyword arguments (e.g. a leftover ``role=`` from an older
    caller) are accepted and ignored - every account has the same
    permissions, so there is nothing to grant here.
    """
    full_name = truncate(full_name, MAX_NAME_LENGTH)
    email = truncate(email, MAX_NAME_LENGTH).lower()
    username = str(username or "").strip()

    if not full_name or not email or not username or not password:
        return False, "All fields are required."
    problem = password_problem(password)
    if problem:
        return False, problem
    if not validate_email(email):
        return False, "Please enter a valid email address."
    if not validate_username(username):
        return False, "Username must be 3-30 characters: letters, numbers, _, ., - only."
    if username_taken(username):
        return False, "That username already exists."

    try:
        new_id = db.execute_returning_id(
            """
            INSERT INTO users (full_name, email, username, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (full_name, email, username, hash_password(password)),
        )
    except IntegrityError:
        return False, "That username already exists."

    log_activity(new_id, "User Registered", f"Account created for {username}")
    return True, "Account created successfully. You can now log in."


def authenticate(username, password) -> tuple[dict | None, str]:
    """Verify credentials and return ``(user, message)``.

    Repeated failures for the same username are throttled, and password hashes
    created by older versions are transparently upgraded on successful login.
    """
    username = str(username or "").strip()
    if not username or not password:
        return None, "Please enter your username and password."

    remaining = lockout_remaining(username)
    if remaining:
        minutes = max(1, remaining // 60)
        return None, f"Too many failed attempts. Try again in about {minutes} minute(s)."

    row = db.fetch_one(
        """
        SELECT id, full_name, email, username, password_hash, created_at
        FROM users
        WHERE LOWER(username) = LOWER(?)
        """,
        (username,),
    )

    if not row or not verify_password(password, row["password_hash"]):
        record_failed_login(username)
        return None, "Invalid username or password."

    if needs_rehash(row["password_hash"]):
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(password), row["id"]),
        )

    clear_failed_logins(username)
    user = {key: value for key, value in row.items() if key != "password_hash"}
    log_activity(user["id"], "Login", f"{user['username']} logged in")
    return user, "Login successful."


def update_profile(
    user_id, full_name, email, current_password="", new_password=""
) -> tuple[bool, str]:
    """Update a profile; changing the password requires the current one."""
    full_name = truncate(full_name, MAX_NAME_LENGTH)
    email = truncate(email, MAX_NAME_LENGTH).lower()

    if not full_name or not email:
        return False, "Full name and email are required."
    if not validate_email(email):
        return False, "Please enter a valid email address."

    new_password = new_password or ""
    if new_password:
        row = db.fetch_one("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        if not row:
            return False, "Account not found."
        if not verify_password(current_password or "", row["password_hash"]):
            return False, "Current password is incorrect."
        problem = password_problem(new_password)
        if problem:
            return False, problem
        db.execute(
            "UPDATE users SET full_name = ?, email = ?, password_hash = ? WHERE id = ?",
            (full_name, email, hash_password(new_password), user_id),
        )
        log_activity(user_id, "Password Changed", "User changed their password")
    else:
        db.execute(
            "UPDATE users SET full_name = ?, email = ? WHERE id = ?",
            (full_name, email, user_id),
        )

    log_activity(user_id, "Profile Updated", "User updated profile information")
    return True, "Profile updated successfully."


def refresh_session_user(user) -> dict | None:
    """Re-read a signed-in user so profile changes take effect without re-login."""
    if not user:
        return None
    return get_user(user["id"])


__all__ = [
    "authenticate",
    "create_user",
    "get_all_users",
    "get_user",
    "refresh_session_user",
    "security",
    "update_profile",
    "user_count",
    "username_taken",
]
