"""Who may do what to a task.

Every account has equal standing - access is decided purely by whether
someone created a task, is assigned to it, or uploaded a given attachment.
These checks are enforced inside the data layer as well as in the UI, so a
stale browser tab or a re-submitted widget cannot mutate somebody else's work.
"""

from __future__ import annotations


def _user_id(user):
    return user.get("id") if user else None


def can_edit_task(task, user) -> bool:
    """The creator and the current assignee may edit a task."""
    if not task or not user:
        return False
    return _user_id(user) in (task.get("creator_id"), task.get("assignee_id"))


def can_delete_task(task, user) -> bool:
    """Only the creator may delete or archive a task."""
    if not task or not user:
        return False
    return _user_id(user) == task.get("creator_id")


def can_manage_attachment(attachment, task, user) -> bool:
    """The uploader and anyone who can edit the task may remove an attachment."""
    if not attachment or not user:
        return False
    if _user_id(user) == attachment.get("user_id"):
        return True
    return can_edit_task(task, user)
