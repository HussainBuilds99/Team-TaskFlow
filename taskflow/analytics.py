"""Filtering, sorting, reporting and CSV export - all pure functions."""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from .config import CATEGORY_OPTIONS, PRIORITY_OPTIONS, STATUS_OPTIONS
from .utils import deadline_flag, is_overdue, tag_list, try_parse_due_date

EXPORT_COLUMNS = [
    "ID",
    "Title",
    "Category",
    "Assigned To",
    "Created By",
    "Due Date",
    "Priority",
    "Status",
    "Progress %",
    "Tags",
    "Recurrence",
    "Archived",
    "Deadline Flag",
]

_PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}
_STATUS_ORDER = {"Pending": 0, "In Progress": 1, "Completed": 2}


@dataclass
class TaskFilters:
    """Every sidebar control in one object, so callers stay readable."""

    search_text: str = ""
    tag_filter: str = ""
    statuses: list = field(default_factory=lambda: list(STATUS_OPTIONS))
    priorities: list = field(default_factory=lambda: list(PRIORITY_OPTIONS))
    categories: list = field(default_factory=lambda: list(CATEGORY_OPTIONS))
    assignee: str = "All"
    mine_only: bool = False
    overdue_only: bool = False
    include_archived: bool = False
    start_date: date | None = None
    end_date: date | None = None


def filter_tasks(tasks, current_user, filters: TaskFilters) -> list[dict]:
    """Apply the sidebar filters to a list of tasks."""
    query = (filters.search_text or "").strip().lower()
    wanted_tags = tag_list(filters.tag_filter)
    statuses = set(filters.statuses or [])
    priorities = set(filters.priorities or [])
    categories = set(filters.categories or [])
    user_id = current_user.get("id") if current_user else None

    results = []
    for task in tasks:
        if filters.mine_only and user_id not in (task["creator_id"], task["assignee_id"]):
            continue
        # Archiving is a separate axis from status: a single checkbox controls it
        # so the status filter never has to be adjusted to see archived work.
        if bool(task.get("archived", 0)) and not filters.include_archived:
            continue
        if statuses and task["status"] not in statuses:
            continue
        if priorities and task["priority"] not in priorities:
            continue
        if categories and task["category"] not in categories:
            continue
        if filters.assignee != "All" and task["assignee_name"] != filters.assignee:
            continue

        if query:
            haystack = " ".join(
                str(task.get(key) or "") for key in ("title", "description", "tags")
            ).lower()
            if query not in haystack:
                continue

        if wanted_tags:
            task_tags = set(tag_list(task.get("tags")))
            if not task_tags.issuperset(wanted_tags):
                continue

        if filters.overdue_only and not is_overdue(task):
            continue

        due = try_parse_due_date(task.get("due_date"))
        if due is None:
            continue
        if filters.start_date and due < filters.start_date:
            continue
        if filters.end_date and due > filters.end_date:
            continue

        results.append(task)
    return results


def sort_tasks(tasks, sort_key) -> list[dict]:
    """Order tasks by one of the sidebar sort options."""
    if sort_key == "Priority":
        return sorted(
            tasks,
            key=lambda task: (_PRIORITY_ORDER.get(task["priority"], 9), task["due_date"]),
        )
    if sort_key == "Status":
        return sorted(
            tasks,
            key=lambda task: (_STATUS_ORDER.get(task["status"], 9), task["due_date"]),
        )
    if sort_key == "Progress":
        return sorted(tasks, key=lambda task: (-int(task.get("progress") or 0), task["due_date"]))
    if sort_key == "Title":
        return sorted(tasks, key=lambda task: task["title"].lower())
    return sorted(
        tasks,
        key=lambda task: (task["due_date"], _PRIORITY_ORDER.get(task["priority"], 9)),
    )


def productivity_summary(tasks, today: date | None = None) -> dict:
    """Headline counters shown in the KPI strip and reports."""
    reference = today or date.today()
    today_iso = reference.isoformat()
    soon_iso = (reference + timedelta(days=2)).isoformat()

    active = [task for task in tasks if not task.get("archived", 0)]
    total = len(tasks)
    completed = sum(task["status"] == "Completed" for task in tasks)
    open_tasks = [task for task in active if task["status"] != "Completed"]

    return {
        "total": total,
        "completed": completed,
        "pending": sum(task["status"] == "Pending" for task in tasks),
        "in_progress": sum(task["status"] == "In Progress" for task in tasks),
        "archived": sum(bool(task.get("archived", 0)) for task in tasks),
        "overdue": sum(task["due_date"] < today_iso for task in open_tasks),
        "due_today": sum(task["due_date"] == today_iso for task in open_tasks),
        "due_soon": sum(today_iso < task["due_date"] <= soon_iso for task in open_tasks),
        "completion_rate": round(completed / total * 100, 1) if total else 0.0,
        "average_progress": (
            round(sum(int(task.get("progress") or 0) for task in tasks) / total, 1)
            if total
            else 0.0
        ),
    }


def build_team_summary(tasks, users, today: date | None = None) -> list[dict]:
    """Per-member workload table."""
    reference = (today or date.today()).isoformat()
    rows = []
    for user in users:
        user_tasks = [task for task in tasks if task["assignee_id"] == user["id"]]
        completed = sum(task["status"] == "Completed" for task in user_tasks)
        overdue = sum(
            task["due_date"] < reference
            and task["status"] != "Completed"
            and not task.get("archived", 0)
            for task in user_tasks
        )
        rows.append(
            {
                "User": user["full_name"],
                "Assigned Tasks": len(user_tasks),
                "Completed Tasks": completed,
                "Pending Tasks": sum(task["status"] == "Pending" for task in user_tasks),
                "In Progress Tasks": sum(task["status"] == "In Progress" for task in user_tasks),
                "Overdue Tasks": overdue,
                "Completion Rate %": (
                    round(completed / len(user_tasks) * 100, 1) if user_tasks else 0.0
                ),
            }
        )
    return rows


def build_workload_rows(tasks, users, today: date | None = None) -> list[dict]:
    """Planner view: open/completed/overdue counts and average progress."""
    reference = (today or date.today()).isoformat()
    rows = []
    for user in users:
        user_tasks = [
            task
            for task in tasks
            if task["assignee_id"] == user["id"] and not task.get("archived", 0)
        ]
        rows.append(
            {
                "User": user["full_name"],
                "Open Tasks": sum(task["status"] != "Completed" for task in user_tasks),
                "Completed": sum(task["status"] == "Completed" for task in user_tasks),
                "Overdue": sum(
                    task["due_date"] < reference and task["status"] != "Completed"
                    for task in user_tasks
                ),
                "Avg Progress %": (
                    round(
                        sum(int(task.get("progress") or 0) for task in user_tasks)
                        / len(user_tasks),
                        1,
                    )
                    if user_tasks
                    else 0.0
                ),
            }
        )
    return rows


def format_task_table(tasks, today: date | None = None) -> list[dict]:
    """Rows for the tasks table and the CSV export."""
    return [
        {
            "ID": task["id"],
            "Title": task["title"],
            "Category": task["category"],
            "Assigned To": task.get("assignee_name", ""),
            "Created By": task.get("creator_name", ""),
            "Due Date": task["due_date"],
            "Priority": task["priority"],
            "Status": task["status"],
            "Progress %": int(task.get("progress") or 0),
            "Tags": task.get("tags", ""),
            "Recurrence": task.get("recurrence", "None"),
            "Archived": "Yes" if task.get("archived", 0) else "No",
            "Deadline Flag": deadline_flag(task, today),
        }
        for task in tasks
    ]


def export_tasks_csv(tasks, today: date | None = None) -> str:
    """Serialise tasks to CSV text that :func:`tasks.import_tasks_from_csv` accepts."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(format_task_table(tasks, today))
    return output.getvalue()


def build_calendar_rows(tasks) -> list[dict]:
    """Group tasks by due date for the calendar table."""
    grouped: dict[str, list[dict]] = {}
    for task in tasks:
        grouped.setdefault(task["due_date"], []).append(task)
    return [
        {
            "Due Date": due_date,
            "Tasks Count": len(grouped[due_date]),
            "Overdue": sum(is_overdue(task) for task in grouped[due_date]),
            "Tasks": ", ".join(task["title"] for task in grouped[due_date]),
        }
        for due_date in sorted(grouped)
    ]


def count_by(tasks, key) -> dict:
    """Counter over a task field, useful for the bar charts."""
    return dict(Counter(task[key] for task in tasks))


def tag_cloud(tasks, limit: int = 15) -> list[dict]:
    """Most used tags across a set of tasks."""
    counter: Counter = Counter()
    for task in tasks:
        counter.update(tag_list(task.get("tags")))
    return [{"Tag": tag, "Tasks": count} for tag, count in counter.most_common(limit)]


def visible_tasks_for(tasks, current_user) -> list[dict]:
    """Tasks a user created or is assigned to, used to scope bulk operations."""
    user_id = current_user.get("id") if current_user else None
    return [
        task for task in tasks if user_id in (task["creator_id"], task["assignee_id"])
    ]
