from taskflow.users import (
    authenticate,
    create_user,
    get_all_users,
    update_profile,
    user_count,
    username_taken,
)


def test_create_user_succeeds():
    success, message = create_user("Admin User", "admin@example.com", "admin", "password123")
    assert success, message
    user = get_all_users()[0]
    assert user["username"] == "admin"
    assert "role" not in user
    assert "password_hash" not in user


def test_every_account_has_equal_standing(admin):
    success, _ = create_user("Second User", "second@example.com", "second", "password123")
    assert success
    second = next(user for user in get_all_users() if user["username"] == "second")
    assert "role" not in second


def test_unknown_kwargs_are_ignored_not_errors(admin):
    """A stray ``role=`` (e.g. from an older caller) must not raise or do anything."""
    success, message = create_user(
        "Sneaky", "sneaky@example.com", "sneaky", "password123", role="Admin"
    )
    assert success, message


def test_duplicate_username_rejected_case_insensitively(admin):
    success, message = create_user("Copy Cat", "copy@example.com", "ADMIN", "password123")
    assert not success
    assert "already exists" in message


def test_weak_password_rejected():
    success, message = create_user("New User", "new@example.com", "newuser", "short")
    assert not success
    assert "at least" in message


def test_invalid_email_rejected():
    success, message = create_user("New User", "not-an-email", "newuser", "password123")
    assert not success
    assert "email" in message.lower()


def test_username_taken_helper(admin):
    assert username_taken("admin")
    assert username_taken("ADMIN")
    assert not username_taken("nobody")


def test_authenticate_succeeds_with_correct_credentials(admin):
    user, message = authenticate("admin", "password123")
    assert user is not None
    assert user["username"] == "admin"
    assert "password_hash" not in user


def test_authenticate_fails_with_wrong_password(admin):
    user, message = authenticate("admin", "wrong-password")
    assert user is None
    assert "invalid" in message.lower()


def test_authenticate_username_is_case_insensitive(admin):
    user, _ = authenticate("Admin", "password123")
    assert user is not None


def test_authenticate_locks_out_after_repeated_failures(admin):
    from taskflow.config import MAX_LOGIN_ATTEMPTS

    for _ in range(MAX_LOGIN_ATTEMPTS):
        authenticate("admin", "wrong-password")
    user, message = authenticate("admin", "password123")
    assert user is None
    assert "too many" in message.lower()


def test_update_profile_requires_current_password_to_change_password(admin):
    success, message = update_profile(
        admin["id"], "Admin User", "admin@example.com", "wrong-current", "newpassword123"
    )
    assert not success
    assert "current password" in message.lower()

    success, message = update_profile(
        admin["id"], "Admin User", "admin@example.com", "password123", "newpassword123"
    )
    assert success
    user, _ = authenticate("admin", "newpassword123")
    assert user is not None


def test_update_profile_without_password_change(admin):
    success, message = update_profile(admin["id"], "Renamed Admin", "admin2@example.com", "", "")
    assert success, message
    refreshed = next(user for user in get_all_users() if user["id"] == admin["id"])
    assert refreshed["full_name"] == "Renamed Admin"
    assert refreshed["email"] == "admin2@example.com"


def test_user_count(admin, member):
    assert user_count() == 2
