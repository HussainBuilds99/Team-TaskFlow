from taskflow.permissions import can_delete_task, can_edit_task, can_manage_attachment


def test_creator_can_edit_and_delete(admin, member, make_task):
    task = make_task(creator=admin, assignee=member)
    assert can_edit_task(task, admin)
    assert can_delete_task(task, admin)


def test_assignee_can_edit_but_not_delete(admin, member, make_task):
    task = make_task(creator=admin, assignee=member)
    assert can_edit_task(task, member)
    assert not can_delete_task(task, member)


def test_unrelated_user_has_no_access(admin, member, other_member, make_task):
    task = make_task(creator=admin, assignee=member)
    assert not can_edit_task(task, other_member)
    assert not can_delete_task(task, other_member)


def test_none_inputs_never_grant_access(admin, make_task):
    task = make_task()
    assert not can_edit_task(None, admin)
    assert not can_edit_task(task, None)
    assert not can_delete_task(task, None)


def test_attachment_uploader_can_always_manage_their_own_upload(admin, other_member, make_task):
    task = make_task(creator=admin, assignee=admin)
    attachment = {"user_id": other_member["id"]}
    assert can_manage_attachment(attachment, task, other_member)


def test_attachment_editors_can_manage_others_uploads(admin, member, other_member, make_task):
    task = make_task(creator=admin, assignee=member)
    attachment = {"user_id": other_member["id"]}
    assert can_manage_attachment(attachment, task, admin)
    assert can_manage_attachment(attachment, task, member)


def test_attachment_unrelated_user_cannot_manage(admin, member, other_member, make_task):
    task = make_task(creator=admin, assignee=admin)
    attachment = {"user_id": member["id"]}
    assert not can_manage_attachment(attachment, task, other_member)
