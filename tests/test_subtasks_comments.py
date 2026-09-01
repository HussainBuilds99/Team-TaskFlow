from taskflow.comments import add_comment, count_comments, delete_comment, get_comments
from taskflow.subtasks import (
    create_subtask,
    delete_subtask,
    get_subtasks,
    set_subtask_done,
    subtask_progress,
)


def test_create_and_toggle_subtask(admin, make_task):
    task = make_task()
    success, message = create_subtask(task["id"], "Do the thing", admin, task)
    assert success, message
    subtasks = get_subtasks(task["id"])
    assert len(subtasks) == 1
    assert subtasks[0]["done"] == 0

    set_subtask_done(subtasks[0]["id"], True, admin, task)
    assert get_subtasks(task["id"])[0]["done"] == 1


def test_subtask_requires_edit_permission(admin, member, other_member, make_task):
    task = make_task(creator=admin, assignee=member)
    success, message = create_subtask(task["id"], "Blocked", other_member, task)
    assert not success
    assert "permission" in message.lower()


def test_empty_subtask_title_rejected(admin, make_task):
    task = make_task()
    success, message = create_subtask(task["id"], "   ", admin, task)
    assert not success


def test_subtask_progress_percentage(admin, make_task):
    task = make_task()
    create_subtask(task["id"], "One", admin, task)
    create_subtask(task["id"], "Two", admin, task)
    subtasks = get_subtasks(task["id"])
    set_subtask_done(subtasks[0]["id"], True, admin, task)
    assert subtask_progress(get_subtasks(task["id"])) == 50


def test_subtask_progress_none_when_empty():
    assert subtask_progress([]) is None


def test_delete_subtask(admin, make_task):
    task = make_task()
    create_subtask(task["id"], "Removable", admin, task)
    subtask_id = get_subtasks(task["id"])[0]["id"]
    delete_subtask(subtask_id, admin, task)
    assert get_subtasks(task["id"]) == []


def test_add_and_list_comments(admin, make_task):
    task = make_task()
    success, message = add_comment(task["id"], admin["id"], "Looks good")
    assert success, message
    comments = get_comments(task["id"])
    assert len(comments) == 1
    assert comments[0]["comment"] == "Looks good"


def test_empty_comment_rejected(admin, make_task):
    task = make_task()
    success, message = add_comment(task["id"], admin["id"], "   ")
    assert not success


def test_comment_author_can_delete_own_comment(admin, member, make_task):
    task = make_task()
    add_comment(task["id"], member["id"], "My comment")
    comment_id = get_comments(task["id"])[0]["id"]
    success, message = delete_comment(comment_id, member)
    assert success, message
    assert get_comments(task["id"]) == []


def test_other_user_cannot_delete_someone_elses_comment(admin, member, other_member, make_task):
    task = make_task()
    add_comment(task["id"], member["id"], "My comment")
    comment_id = get_comments(task["id"])[0]["id"]
    success, message = delete_comment(comment_id, other_member)
    assert not success
    assert len(get_comments(task["id"])) == 1


def test_count_comments_across_multiple_tasks(admin, make_task):
    task_one = make_task(title="One")
    task_two = make_task(title="Two")
    add_comment(task_one["id"], admin["id"], "a")
    add_comment(task_one["id"], admin["id"], "b")
    counts = count_comments([task_one["id"], task_two["id"]])
    assert counts[task_one["id"]] == 2
    assert counts[task_two["id"]] == 0
