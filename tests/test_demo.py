from datetime import date, timedelta

from taskflow import db
from taskflow.demo import GUEST_USERNAME, start_guest_session
from taskflow.tasks import archive_task, bulk_update_tasks, get_task, get_tasks
from taskflow.users import authenticate


def _guest_tasks(guest):
    return [
        task
        for task in get_tasks()
        if guest["id"] in (task["creator_id"], task["assignee_id"]) and not task["archived"]
    ]


def test_guest_session_creates_account_and_sample_tasks():
    guest, _ = start_guest_session()
    assert guest is not None
    assert guest["username"] == GUEST_USERNAME
    assert "password_hash" not in guest
    assert len(_guest_tasks(guest)) == 5


def test_guest_session_is_idempotent():
    first, _ = start_guest_session()
    second, _ = start_guest_session()
    assert first["id"] == second["id"]
    assert len(_guest_tasks(second)) == 5


def test_guest_tasks_are_reseeded_once_all_are_archived():
    guest, _ = start_guest_session()
    for task in _guest_tasks(guest):
        if task["creator_id"] == guest["id"]:
            archive_task(task["id"], guest)
    assert _guest_tasks(guest) == []

    start_guest_session()
    assert len(_guest_tasks(guest)) == 5


def test_guest_cannot_log_in_through_the_password_form():
    start_guest_session()
    user, _ = authenticate(GUEST_USERNAME, "")
    assert user is None
    user, _ = authenticate(GUEST_USERNAME, "TaskFlowDemo1")
    assert user is None


def test_bulk_restore_with_new_status_applies_the_new_status(admin, make_task):
    task = make_task(title="Restore me", status="In Progress")
    archive_task(task["id"], admin)

    success, message = bulk_update_tasks([task["id"]], admin, status="Completed", archive=False)
    assert success, message

    restored = get_task(task["id"])
    assert restored["archived"] == 0
    assert restored["status"] == "Completed"
    assert restored["progress"] == 100
    assert restored["previous_status"] is None


def test_bulk_restore_without_status_brings_back_previous_status(admin, make_task):
    task = make_task(title="Restore me too", status="In Progress")
    archive_task(task["id"], admin)

    success, message = bulk_update_tasks([task["id"]], admin, archive=False)
    assert success, message

    restored = get_task(task["id"])
    assert restored["archived"] == 0
    assert restored["status"] == "In Progress"


def test_guest_session_moves_stale_sample_dates_back_to_today():
    guest, _ = start_guest_session()
    db.execute("UPDATE tasks SET due_date = ? WHERE creator_id = ?", ("2000-01-01", guest["id"]))

    start_guest_session()
    due_dates = [task["due_date"] for task in _guest_tasks(guest)]
    assert "2000-01-01" not in due_dates
    assert min(due_dates) >= (date.today() - timedelta(days=1)).isoformat()
