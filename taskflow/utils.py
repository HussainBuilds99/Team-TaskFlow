"""Small, dependency-free helpers shared across the app."""

from __future__ import annotations

import calendar
import html
from datetime import date, datetime, timedelta

from .config import MAX_TAG_LENGTH, MAX_TAGS

DATE_FORMAT = "%Y-%m-%d"


def escape_html(value) -> str:
    """Escape a value for safe interpolation into raw HTML.

    Every string that reaches ``st.markdown(..., unsafe_allow_html=True)`` has to
    go through this: task titles, names and tags are user supplied, so without
    escaping a value such as ``<img src=x onerror=alert(1)>`` would execute for
    every teammate who views the board.
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def clamp_int(value, low: int, high: int, default: int = 0) -> int:
    """Coerce ``value`` to an int inside ``[low, high]``, falling back to default."""
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def parse_due_date(value) -> date:
    """Parse a ``YYYY-MM-DD`` string (or date/datetime) into a ``date``.

    Raises ``ValueError`` when the value cannot be interpreted.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value).strip(), DATE_FORMAT).date()


def try_parse_due_date(value, fallback: date | None = None) -> date | None:
    """Like :func:`parse_due_date` but returns ``fallback`` instead of raising."""
    try:
        return parse_due_date(value)
    except (ValueError, TypeError):
        return fallback


def format_date(value) -> str:
    """Render a date-ish value as ``YYYY-MM-DD``."""
    parsed = try_parse_due_date(value)
    return parsed.isoformat() if parsed else ""


def add_months(base: date, months: int) -> date:
    """Add calendar months, clamping to the last valid day of the target month.

    ``2024-01-31`` plus one month is ``2024-02-29`` rather than a rolling 30 days.
    """
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def next_due_date(current_due_date, recurrence: str) -> date:
    """Next occurrence of a recurring task, based on its current due date."""
    base = parse_due_date(current_due_date)
    if recurrence == "Daily":
        return base + timedelta(days=1)
    if recurrence == "Weekly":
        return base + timedelta(days=7)
    if recurrence == "Monthly":
        return add_months(base, 1)
    return base


def tag_list(raw_tags) -> list[str]:
    """Split a stored tag string into a de-duplicated, normalised list."""
    if not raw_tags:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in str(raw_tags).split(","):
        tag = " ".join(item.split()).lower()[:MAX_TAG_LENGTH]
        if tag and tag not in seen:
            seen.add(tag)
            cleaned.append(tag)
        if len(cleaned) >= MAX_TAGS:
            break
    return cleaned


def normalize_tags(raw_tags) -> str:
    """Normalise free-text tag input into the canonical comma separated form."""
    return ",".join(tag_list(raw_tags))


def truncate(text, limit: int) -> str:
    """Trim surrounding whitespace and cap the length of a user supplied string."""
    if text is None:
        return ""
    return str(text).strip()[:limit]


def is_overdue(task, today: date | None = None) -> bool:
    """True when a task's due date has passed and it is not completed."""
    reference = (today or date.today()).isoformat()
    return bool(
        task.get("due_date")
        and task["due_date"] < reference
        and task.get("status") != "Completed"
        and not task.get("archived", 0)
    )


def deadline_flag(task, today: date | None = None) -> str:
    """Human readable deadline state used by tables and exports."""
    reference = (today or date.today()).isoformat()
    if task.get("archived", 0):
        return "Archived"
    if task.get("status") == "Completed":
        return "Completed"
    if task.get("due_date", "") < reference:
        return "Overdue"
    if task.get("due_date", "") == reference:
        return "Due Today"
    return "On Track"
