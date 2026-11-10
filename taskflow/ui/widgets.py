"""Display helpers: coloured badges, friendly dates and cached reads."""

from __future__ import annotations

import re
from datetime import date

import streamlit as st

from ..tasks import get_tasks
from ..users import get_all_users
from ..utils import is_overdue, try_parse_due_date

PRIORITY_COLORS = {"High": "red", "Medium": "orange", "Low": "green"}
STATUS_COLORS = {"Pending": "gray", "In Progress": "blue", "Completed": "green"}

# Characters that would otherwise be read as Markdown (or as Streamlit's
# ":color[...]" directives) when user text is placed in a label.
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#+\-.!|~:$])")


@st.cache_data(ttl=20, show_spinner=False)
def load_tasks() -> list[dict]:
    """Every task, cached briefly; any change made in the app clears the cache."""
    return get_tasks()


@st.cache_data(ttl=20, show_spinner=False)
def load_users() -> list[dict]:
    """Every account, cached briefly; any change made in the app clears the cache."""
    return get_all_users()


def md_escape(text) -> str:
    """Make user text safe to place inside Streamlit Markdown."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", str(text or ""))


def badge(text, color: str) -> str:
    return f":{color}-badge[{md_escape(text)}]"


def due_label(task, today: date | None = None) -> str:
    """'Due today', '3 days overdue', 'Due Nov 14' and so on."""
    today = today or date.today()
    due = try_parse_due_date(task.get("due_date"))
    if due is None:
        return "No due date"

    if due.year == today.year:
        pretty = f"{due:%b} {due.day}"
    else:
        pretty = f"{due:%b} {due.day}, {due.year}"
    if task.get("status") == "Completed" or task.get("archived", 0):
        return f"Due {pretty}"

    days = (due - today).days
    if days < 0:
        return f"{-days} day{'s' if days != -1 else ''} overdue"
    if days == 0:
        return "Due today"
    if days == 1:
        return "Due tomorrow"
    if days < 7:
        return f"Due in {days} days"
    return f"Due {pretty}"


def task_header(task) -> str:
    """One-line expander label: title, coloured priority/status and due date."""
    priority = task["priority"]
    status = task["status"]
    due = due_label(task)
    parts = [
        f"**{md_escape(task['title'])}**",
        f":{PRIORITY_COLORS.get(priority, 'gray')}[{md_escape(priority)}]",
        f":{STATUS_COLORS.get(status, 'gray')}[{md_escape(status)}]",
        f":red[{due}]" if is_overdue(task) else due,
    ]
    if task.get("archived", 0):
        parts.append(":gray[Archived]")
    return "  ·  ".join(parts)


def render_task_badges(task) -> None:
    """Priority, status, category, progress and repeat badges for one task."""
    badges = [
        badge(f"{task['priority']} priority", PRIORITY_COLORS.get(task["priority"], "gray")),
        badge(task["status"], STATUS_COLORS.get(task["status"], "gray")),
        badge(task["category"], "violet"),
        badge(f"{int(task.get('progress') or 0)}% done", "blue"),
    ]
    if task.get("recurrence", "None") != "None":
        badges.append(badge(f"Repeats {task['recurrence'].lower()}", "gray"))
    if task.get("archived", 0):
        badges.append(badge("Archived", "gray"))
    st.markdown(" ".join(badges))

    tags = task.get("tags")
    if tags:
        st.caption("Tags: " + ", ".join(md_escape(tag) for tag in tags.split(",")))
