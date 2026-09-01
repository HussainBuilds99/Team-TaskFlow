from taskflow.attachments import (
    count_attachments,
    delete_attachment,
    get_attachments,
    read_attachment,
    safe_display_name,
    save_attachment,
    validate_upload,
)
from tests.conftest import FakeUpload


def test_safe_display_name_strips_path_and_unsafe_characters():
    assert safe_display_name("../../etc/passwd") == "passwd"
    assert safe_display_name("my report (final)!!.pdf") == "my_report_final_.pdf"


def test_validate_upload_rejects_disallowed_extension():
    ok, message = validate_upload(FakeUpload("virus.exe"))
    assert not ok
    assert "not allowed" in message


def test_validate_upload_rejects_oversized_file():
    from taskflow.config import MAX_ATTACHMENT_SIZE_BYTES

    big = FakeUpload("big.txt", data=b"x" * (MAX_ATTACHMENT_SIZE_BYTES + 1))
    ok, message = validate_upload(big)
    assert not ok
    assert "too large" in message


def test_validate_upload_rejects_empty_file():
    ok, message = validate_upload(FakeUpload("empty.txt", data=b""))
    assert not ok


def test_validate_upload_accepts_allowed_type():
    ok, _ = validate_upload(FakeUpload("notes.txt", data=b"hello"))
    assert ok


def test_save_and_read_attachment_round_trip(admin, make_task):
    task = make_task()
    success, message = save_attachment(
        task["id"], admin["id"], FakeUpload("notes.txt", b"hello world"), task, admin
    )
    assert success, message
    attachments = get_attachments(task["id"])
    assert len(attachments) == 1
    assert read_attachment(attachments[0]) == b"hello world"


def test_two_uploads_with_same_name_do_not_collide(admin, make_task):
    task = make_task()
    save_attachment(task["id"], admin["id"], FakeUpload("notes.txt", b"first"), task, admin)
    save_attachment(task["id"], admin["id"], FakeUpload("notes.txt", b"second"), task, admin)
    attachments = get_attachments(task["id"])
    assert len(attachments) == 2
    contents = {read_attachment(attachment) for attachment in attachments}
    assert contents == {b"first", b"second"}


def test_save_attachment_denied_without_edit_permission(admin, member, other_member, make_task):
    task = make_task(creator=admin, assignee=member)
    success, message = save_attachment(
        task["id"], other_member["id"], FakeUpload("notes.txt"), task, other_member
    )
    assert not success
    assert "permission" in message.lower()


def test_delete_attachment_removes_row_and_file(admin, make_task):
    task = make_task()
    save_attachment(task["id"], admin["id"], FakeUpload("notes.txt", b"data"), task, admin)
    attachment = get_attachments(task["id"])[0]
    success, message = delete_attachment(attachment["id"], admin, task)
    assert success, message
    assert get_attachments(task["id"]) == []


def test_delete_attachment_denied_for_unrelated_user(admin, member, other_member, make_task):
    task = make_task(creator=admin, assignee=admin)
    save_attachment(task["id"], admin["id"], FakeUpload("notes.txt"), task, admin)
    attachment = get_attachments(task["id"])[0]
    success, message = delete_attachment(attachment["id"], other_member, task)
    assert not success
    assert len(get_attachments(task["id"])) == 1


def test_count_attachments_across_tasks(admin, make_task):
    task_one = make_task(title="One")
    task_two = make_task(title="Two")
    save_attachment(task_one["id"], admin["id"], FakeUpload("a.txt"), task_one, admin)
    counts = count_attachments([task_one["id"], task_two["id"]])
    assert counts[task_one["id"]] == 1
    assert counts[task_two["id"]] == 0


def test_read_attachment_refuses_paths_outside_upload_dir(tmp_path):
    outside_file = tmp_path / "outside.txt"
    outside_file.write_bytes(b"should not be readable")
    fake_attachment = {"file_path": str(outside_file)}
    assert read_attachment(fake_attachment) is None
