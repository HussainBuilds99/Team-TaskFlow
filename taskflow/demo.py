"""One-click sample data so the workspace can be demonstrated quickly."""

from __future__ import annotations

from datetime import date, timedelta

from . import db
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
