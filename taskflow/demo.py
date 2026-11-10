"""One-click sample data so the workspace can be demonstrated quickly."""

from __future__ import annotations

import secrets
import threading
from collections import defaultdict
from datetime import date, timedelta

from . import db
from .activity import log_activity
from .tasks import create_task
from .users import create_user, get_all_users

DEMO_PASSWORD = "TaskFlowDemo1"

DEMO_USERS = (
    ("Aisha Khan", "aisha@example.com", "aisha"),
    ("Omar Ali", "omar@example.com", "omar"),
    ("Sara Noor", "sara@example.com", "sara"),
)


def _demo_tasks(user_map):
    today = date.today()
    return (
        (
            "Prepare project proposal",
            "Draft the final proposal document.",
            "Research",
            user_map["aisha"],
            today,
            "High",
            "In Progress",
            55,
            "proposal,research",
        ),
        (
            "Design presentation slides",
            "Create slides for the class presentation.",
            "Presentation",
            user_map["omar"],
            today + timedelta(days=2),
            "Medium",
            "Pending",
            15,
            "slides,design",
        ),
        (
            "Team meeting",
            "Discuss progress and assign remaining work.",
            "Meeting",
            user_map["sara"],
            today + timedelta(days=1),
            "Low",
            "Pending",
            5,
            "meeting",
        ),
        (
            "Write introduction section",
            "Complete the introduction and objectives.",
            "Assignment",
            user_map["aisha"],
            today - timedelta(days=1),
            "High",
            "Pending",
            35,
            "report,writing",
        ),
        (
            "Collect references",
            "Find supporting sources and examples.",
            "Research",
            user_map["omar"],
            today + timedelta(days=4),
            "Medium",
            "Completed",
            100,
            "citations",
        ),
    )


def seed_demo_data(admin_user) -> tuple[bool, str]:
    """Add three demo teammates and a handful of tasks to an empty workspace."""
    row = db.fetch_one("SELECT COUNT(*) AS count FROM tasks")
    if row and row["count"] > 0:
        return False, "Demo data was not added because tasks already exist."

    for full_name, email, username in DEMO_USERS:
        create_user(full_name, email, username, DEMO_PASSWORD)

    user_map = {user["username"]: user["id"] for user in get_all_users()}
    missing = [username for _, _, username in DEMO_USERS if username not in user_map]
    if missing:
        return False, f"Could not create demo account(s): {', '.join(missing)}."

    created = 0
    for title, description, category, assignee_id, due, priority, status, progress, tags in _demo_tasks(
        user_map
    ):
        success, _ = create_task(
            title,
            description,
            category,
            admin_user["id"],
            assignee_id,
            due.isoformat(),
            priority,
            status,
            progress,
            tags,
        )
        created += int(success)

    return True, (
        f"Added {len(DEMO_USERS)} demo teammates and {created} tasks. "
        f"They all sign in with the password '{DEMO_PASSWORD}'."
    )


# --- One-click guest demo ---------------------------------------------------
# Lets a visitor (e.g. a recruiter following a portfolio link) explore the app
# without registering. Everyone who clicks "Try the demo" shares one guest
# account; its sample tasks are re-created whenever none are left active.

GUEST_USERNAME = "demo_guest"
GUEST_FULL_NAME = "Demo Visitor"
GUEST_EMAIL = "demo_guest@example.com"

_guest_lock = threading.Lock()


def _guest_row() -> dict | None:
    return db.fetch_one(
        "SELECT id, full_name, email, username, created_at FROM users "
        "WHERE LOWER(username) = LOWER(?)",
        (GUEST_USERNAME,),
    )


def _ensure_guest_tasks(guest) -> None:
    """Give the guest a fresh set of sample tasks when it has no active ones."""
    row = db.fetch_one(
        "SELECT COUNT(*) AS count FROM tasks "
        "WHERE archived = 0 AND (creator_id = ? OR assignee_id = ?)",
        (guest["id"], guest["id"]),
    )
    if row and row["count"] > 0:
        return

    for full_name, email, username in DEMO_USERS:
        create_user(full_name, email, username, DEMO_PASSWORD)
    user_map = {user["username"]: user["id"] for user in get_all_users()}

    for index, (title, description, category, assignee_id, due, priority, status, progress, tags) in enumerate(
        _demo_tasks(user_map)
    ):
        # Every other task goes to the guest, so "Only my tasks" and the
        # edit/delete controls have something to show straight away.
        assignee = guest["id"] if index % 2 == 0 else assignee_id
        create_task(
            title,
            description,
            category,
            guest["id"],
            assignee,
            due.isoformat(),
            priority,
            status,
            progress,
            tags,
        )


def _refresh_guest_dates(guest) -> None:
    """Move the sample tasks back to their usual due dates relative to today.

    The samples are created once, so without this the demo would look more and
    more overdue with every day that passes after it was first opened.
    """
    for title, _description, _category, _assignee, due, *_rest in _demo_tasks(
        defaultdict(lambda: None)
    ):
        db.execute(
            "UPDATE tasks SET due_date = ? WHERE creator_id = ? AND title = ? AND due_date <> ?",
            (due.isoformat(), guest["id"], title, due.isoformat()),
        )


def start_guest_session() -> tuple[dict | None, str]:
    """Return the shared guest account (creating it and its sample data if needed)."""
    with _guest_lock:
        guest = _guest_row()
        if guest is None:
            # A random password nobody knows: the guest is reachable only through
            # this button, never through the normal login form.
            create_user(GUEST_FULL_NAME, GUEST_EMAIL, GUEST_USERNAME, secrets.token_urlsafe(24))
            guest = _guest_row()
        if guest is None:
            return None, "The demo is unavailable right now. Please register instead."
        _ensure_guest_tasks(guest)
        _refresh_guest_dates(guest)

    log_activity(guest["id"], "Login", "Guest started a demo session")
    return guest, "You're exploring the demo workspace."
