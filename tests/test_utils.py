from datetime import date

from taskflow.utils import (
    add_months,
    clamp_int,
    deadline_flag,
    escape_html,
    is_overdue,
    next_due_date,
    normalize_tags,
    parse_due_date,
    tag_list,
    truncate,
    try_parse_due_date,
)


def test_escape_html_neutralises_script_tags():
    dangerous = "<img src=x onerror=alert(1)>"
    escaped = escape_html(dangerous)
    assert "<img" not in escaped
    assert "&lt;img" in escaped


def test_escape_html_handles_none():
    assert escape_html(None) == ""


def test_clamp_int_bounds_and_bad_input():
    assert clamp_int(150, 0, 100) == 100
    assert clamp_int(-5, 0, 100) == 0
    assert clamp_int("not a number", 0, 100, default=7) == 7
    assert clamp_int("42", 0, 100) == 42


def test_parse_due_date_accepts_strings_and_dates():
    assert parse_due_date("2030-01-15") == date(2030, 1, 15)
    assert parse_due_date(date(2030, 1, 15)) == date(2030, 1, 15)


def test_try_parse_due_date_falls_back_on_bad_input():
    assert try_parse_due_date("not-a-date") is None
    assert try_parse_due_date("not-a-date", date(2030, 1, 1)) == date(2030, 1, 1)


def test_add_months_clamps_to_last_valid_day():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert add_months(date(2024, 1, 15), 1) == date(2024, 2, 15)


def test_next_due_date_recurrence_rules():
    assert next_due_date("2030-01-01", "Daily") == date(2030, 1, 2)
    assert next_due_date("2030-01-01", "Weekly") == date(2030, 1, 8)
    assert next_due_date("2030-01-31", "Monthly") == date(2030, 2, 28)
    assert next_due_date("2030-01-01", "None") == date(2030, 1, 1)


def test_tag_list_normalises_and_deduplicates():
    assert tag_list("Urgent, urgent , Design,, backend") == ["urgent", "design", "backend"]
    assert tag_list("") == []
    assert tag_list(None) == []


def test_tag_list_caps_count():
    raw = ",".join(f"tag{i}" for i in range(50))
    assert len(tag_list(raw)) <= 12


def test_normalize_tags_round_trips_through_tag_list():
    assert normalize_tags("A, b, a") == "a,b"


def test_truncate_strips_and_caps_length():
    assert truncate("  hello  ", 10) == "hello"
    assert truncate("a" * 20, 5) == "aaaaa"
    assert truncate(None, 5) == ""


def test_is_overdue_true_only_for_past_incomplete_active_tasks():
    today = date(2030, 6, 15)
    overdue_task = {"due_date": "2030-06-14", "status": "Pending", "archived": 0}
    assert is_overdue(overdue_task, today)

    completed_task = {"due_date": "2030-06-14", "status": "Completed", "archived": 0}
    assert not is_overdue(completed_task, today)

    archived_task = {"due_date": "2030-06-14", "status": "Pending", "archived": 1}
    assert not is_overdue(archived_task, today)

    future_task = {"due_date": "2030-06-20", "status": "Pending", "archived": 0}
    assert not is_overdue(future_task, today)


def test_deadline_flag_variants():
    today = date(2030, 6, 15)
    assert deadline_flag({"due_date": "2030-06-14", "status": "Pending", "archived": 0}, today) == "Overdue"
    assert deadline_flag({"due_date": "2030-06-15", "status": "Pending", "archived": 0}, today) == "Due Today"
    assert deadline_flag({"due_date": "2030-06-20", "status": "Pending", "archived": 0}, today) == "On Track"
    assert deadline_flag({"due_date": "2030-06-01", "status": "Completed", "archived": 0}, today) == "Completed"
    assert deadline_flag({"due_date": "2030-06-01", "status": "Pending", "archived": 1}, today) == "Archived"
