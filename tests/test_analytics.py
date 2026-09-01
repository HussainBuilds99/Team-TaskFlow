from datetime import date

from taskflow.analytics import (
    TaskFilters,
    build_team_summary,
    export_tasks_csv,
    filter_tasks,
    format_task_table,
    productivity_summary,
    sort_tasks,
    visible_tasks_for,
)
from taskflow.tasks import import_tasks_from_csv


def test_filter_tasks_excludes_archived_by_default(admin, make_task):
    from taskflow.tasks import archive_task, get_tasks

    task = make_task()
    archive_task(task["id"], admin)
    tasks = get_tasks()

    visible = filter_tasks(tasks, admin, TaskFilters())
    assert task["id"] not in [t["id"] for t in visible]

    visible_with_archived = filter_tasks(tasks, admin, TaskFilters(include_archived=True))
    assert task["id"] in [t["id"] for t in visible_with_archived]


def test_filter_tasks_mine_only_uses_creator_or_assignee(admin, member, other_member, make_task):
    from taskflow.tasks import get_tasks

    mine = make_task(creator=member, assignee=member, title="Mine")
    make_task(creator=admin, assignee=other_member, title="Not mine")
    tasks = get_tasks()

    visible = filter_tasks(tasks, member, TaskFilters(mine_only=True))
    assert [t["id"] for t in visible] == [mine["id"]]


def test_filter_tasks_search_covers_title_description_and_tags(admin, make_task):
    from taskflow.tasks import get_tasks

    make_task(title="Unrelated", tags="alpha")
    make_task(title="Findme", tags="")
    tasks = get_tasks()

    by_title = filter_tasks(tasks, admin, TaskFilters(search_text="findme"))
    assert len(by_title) == 1

    by_tag = filter_tasks(tasks, admin, TaskFilters(search_text="alpha"))
    assert len(by_tag) == 1


def test_filter_tasks_tag_filter_requires_all_requested_tags(admin, make_task):
    from taskflow.tasks import get_tasks

    make_task(title="Has both", tags="urgent,design")
    make_task(title="Has one", tags="urgent")
    tasks = get_tasks()

    matches = filter_tasks(tasks, admin, TaskFilters(tag_filter="urgent,design"))
    assert [t["title"] for t in matches] == ["Has both"]


def test_filter_tasks_date_window(admin, make_task):
    from taskflow.tasks import get_tasks

    make_task(title="Early", due_date="2030-01-01")
    make_task(title="Late", due_date="2030-06-01")
    tasks = get_tasks()

    matches = filter_tasks(
        tasks,
        admin,
        TaskFilters(start_date=date(2030, 2, 1), end_date=date(2030, 12, 31)),
    )
    assert [t["title"] for t in matches] == ["Late"]


def test_sort_tasks_by_priority():
    tasks = [
        {"priority": "Low", "due_date": "2030-01-01", "title": "c", "status": "Pending", "progress": 0},
        {"priority": "High", "due_date": "2030-01-02", "title": "a", "status": "Pending", "progress": 0},
        {"priority": "Medium", "due_date": "2030-01-03", "title": "b", "status": "Pending", "progress": 0},
    ]
    ordered = sort_tasks(tasks, "Priority")
    assert [task["priority"] for task in ordered] == ["High", "Medium", "Low"]


def test_productivity_summary_counts_overdue_and_completion_rate():
    today = date(2030, 6, 15)
    tasks = [
        {"status": "Completed", "due_date": "2030-06-01", "progress": 100, "archived": 0},
        {"status": "Pending", "due_date": "2030-06-01", "progress": 0, "archived": 0},
        {"status": "In Progress", "due_date": "2030-06-16", "progress": 50, "archived": 0},
        {"status": "Pending", "due_date": "2030-06-01", "progress": 0, "archived": 1},
    ]
    summary = productivity_summary(tasks, today)
    assert summary["total"] == 4
    assert summary["completed"] == 1
    assert summary["overdue"] == 1  # archived task is excluded
    assert summary["completion_rate"] == 25.0


def test_build_team_summary_scopes_to_assignee(admin, member, make_task):
    make_task(creator=admin, assignee=member, status="Completed")
    make_task(creator=admin, assignee=member, status="Pending")
    from taskflow.tasks import get_tasks
    from taskflow.users import get_all_users

    summary = build_team_summary(get_tasks(), get_all_users())
    member_row = next(row for row in summary if row["User"] == "Member User")
    assert member_row["Assigned Tasks"] == 2
    assert member_row["Completed Tasks"] == 1
    assert member_row["Completion Rate %"] == 50.0


def test_export_then_reimport_round_trip(admin, make_task):
    from taskflow.tasks import get_tasks

    make_task(title="Round trip task", tags="one,two", progress=42)
    csv_text = export_tasks_csv(get_tasks())

    success, message = import_tasks_from_csv(csv_text.encode("utf-8"), admin["id"], admin["id"])
    assert success, message
    titles = [task["title"] for task in get_tasks()]
    assert titles.count("Round trip task") == 2


def test_format_task_table_deadline_flags(admin, make_task):
    task = make_task(due_date="2020-01-01", status="Pending")
    rows = format_task_table([task], today=date(2030, 1, 1))
    assert rows[0]["Deadline Flag"] == "Overdue"


def test_visible_tasks_for_scopes_to_creator_or_assignee(admin, member, other_member, make_task):
    from taskflow.tasks import get_tasks

    make_task(creator=admin, assignee=admin, title="Admin's own")
    make_task(creator=member, assignee=other_member, title="Unrelated to admin")
    tasks = get_tasks()
    assert len(visible_tasks_for(tasks, admin)) == 1
    assert len(visible_tasks_for(tasks, other_member)) == 1
