from taskflow.tasks import (
    archive_task,
    bulk_update_tasks,
    create_next_recurring_task,
    create_task,
    delete_task,
    get_task,
    get_tasks,
    import_tasks_from_csv,
    restore_task,
    set_task_status,
    update_task,
)


def test_create_task_requires_minimum_title_length(admin):
    success, message = create_task(
        "ab", "d", "Other", admin["id"], admin["id"], "2030-01-01", "High", "Pending"
    )
    assert not success
    assert "3 characters" in message


def test_create_task_rejects_unknown_assignee(admin):
    success, message = create_task(
        "Valid title", "d", "Other", admin["id"], 999999, "2030-01-01", "High", "Pending"
    )
    assert not success
    assert "assignee" in message.lower()


def test_create_task_rejects_bad_due_date(admin):
    success, message = create_task(
        "Valid title", "d", "Other", admin["id"], admin["id"], "not-a-date", "High", "Pending"
    )
    assert not success
    assert "date" in message.lower()


def test_completed_task_is_forced_to_full_progress(admin, make_task):
    task = make_task(status="Completed", progress=10)
    assert task["progress"] == 100


def test_update_task_denied_for_unrelated_user(admin, member, other_member, make_task):
    task = make_task(creator=admin, assignee=member)
    success, message = update_task(
        task["id"],
        other_member,
        "New title",
        "d",
        "Other",
        member["id"],
        "2030-02-01",
        "High",
        "Pending",
    )
    assert not success
    assert "permission" in message.lower()


def test_assignee_can_edit_task(admin, member, make_task):
    task = make_task(creator=admin, assignee=member)
    success, message = update_task(
        task["id"], member, "Updated title", "d", "Other", member["id"], "2030-02-01", "High", "Pending"
    )
    assert success, message
    assert get_task(task["id"])["title"] == "Updated title"


def test_set_task_status_sets_full_progress_on_completion(admin, make_task):
    task = make_task(status="Pending", progress=20)
    success, message = set_task_status(task["id"], admin, "Completed")
    assert success, message
    assert get_task(task["id"])["progress"] == 100


def test_archive_then_restore_preserves_previous_status(admin, make_task):
    task = make_task(status="In Progress", progress=40)
    archive_task(task["id"], admin)
    archived = get_task(task["id"])
    assert archived["archived"] == 1

    restore_task(task["id"], admin)
    restored = get_task(task["id"])
    assert restored["archived"] == 0
    assert restored["status"] == "In Progress"


def test_only_creator_can_archive(admin, member, other_member, make_task):
    task = make_task(creator=admin, assignee=member)
    success, message = archive_task(task["id"], other_member)
    assert not success
    assert "creator" in message.lower()

    # The assignee alone (not the creator) also cannot archive.
    success, message = archive_task(task["id"], member)
    assert not success


def test_delete_task_removes_row(admin, make_task):
    task = make_task()
    success, message = delete_task(task["id"], admin)
    assert success, message
    assert get_task(task["id"]) is None


def test_delete_task_denied_for_non_creator(admin, member, make_task):
    task = make_task(creator=admin, assignee=member)
    success, message = delete_task(task["id"], member)
    assert not success
    assert get_task(task["id"]) is not None


def test_recurring_task_creates_next_cycle_with_advanced_due_date(admin, make_task):
    task = make_task(due_date="2030-01-01", recurrence="Weekly")
    success, message = create_next_recurring_task(task, admin)
    assert success, message
    titles = [t for t in get_tasks() if t["title"] == task["title"]]
    assert len(titles) == 2
    due_dates = sorted(t["due_date"] for t in titles)
    assert due_dates == ["2030-01-01", "2030-01-08"]


def test_recurring_task_does_not_duplicate(admin, make_task):
    task = make_task(due_date="2030-01-01", recurrence="Weekly")
    create_next_recurring_task(task, admin)
    success, message = create_next_recurring_task(task, admin)
    assert not success
    assert "already exists" in message.lower()


def test_non_recurring_task_cannot_spawn_next_cycle(admin, make_task):
    task = make_task(recurrence="None")
    success, message = create_next_recurring_task(task, admin)
    assert not success


def test_bulk_update_only_applies_to_permitted_tasks(admin, member, other_member, make_task):
    own_task = make_task(creator=member, assignee=member, title="Owned by member")
    foreign_task = make_task(creator=admin, assignee=other_member, title="Owned by admin")

    success, message = bulk_update_tasks(
        [own_task["id"], foreign_task["id"]], member, status="Completed"
    )
    assert success, message
    assert "1 task" in message
    assert get_task(own_task["id"])["status"] == "Completed"
    assert get_task(foreign_task["id"])["status"] != "Completed"


def test_bulk_archive_records_previous_status_for_restore(admin, make_task):
    task = make_task(status="In Progress")
    bulk_update_tasks([task["id"]], admin, archive=True)
    assert get_task(task["id"])["archived"] == 1

    bulk_update_tasks([task["id"]], admin, archive=False)
    restored = get_task(task["id"])
    assert restored["archived"] == 0
    assert restored["status"] == "In Progress"


def test_import_tasks_from_csv_requires_columns(admin):
    success, message = import_tasks_from_csv(b"Foo,Bar\n1,2\n", admin["id"], admin["id"])
    assert not success
    assert "missing" in message.lower()


def test_import_tasks_from_csv_creates_valid_rows_and_skips_bad_ones(admin):
    csv_bytes = (
        b"Title,Due Date,Priority,Status\n"
        b"Good task,2030-05-01,High,Pending\n"
        b",2030-05-02,High,Pending\n"
        b"Another good task,not-a-date,Medium,Pending\n"
    )
    success, message = import_tasks_from_csv(csv_bytes, admin["id"], admin["id"])
    assert success, message
    assert "Imported 1" in message
    assert "skipped 2" in message.lower()


def test_import_tasks_from_csv_defaults_invalid_choice_fields(admin):
    csv_bytes = b"Title,Due Date,Priority,Status,Category\nTask X,2030-05-01,Nonsense,Nonsense,Nonsense\n"
    success, message = import_tasks_from_csv(csv_bytes, admin["id"], admin["id"])
    assert success, message
    imported = next(task for task in get_tasks() if task["title"] == "Task X")
    assert imported["priority"] == "Medium"
    assert imported["status"] == "Pending"
    assert imported["category"] == "Other"
