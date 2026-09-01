import time

from taskflow import security


def test_hash_password_roundtrip():
    hashed = security.hash_password("correct horse battery staple")
    assert hashed.startswith("pbkdf2_sha256$")
    assert security.verify_password("correct horse battery staple", hashed)


def test_verify_password_rejects_wrong_password():
    hashed = security.hash_password("correct horse battery staple")
    assert not security.verify_password("wrong password", hashed)


def test_verify_password_handles_garbage_hash():
    assert not security.verify_password("anything", "not-a-real-hash")
    assert not security.verify_password("anything", None)
    assert not security.verify_password("anything", "pbkdf2_sha256$notanumber$salt$digest")


def test_legacy_sha256_hash_still_verifies():
    import hashlib

    legacy_hash = hashlib.sha256(b"legacy-password").hexdigest()
    assert security.verify_password("legacy-password", legacy_hash)
    assert not security.verify_password("wrong", legacy_hash)


def test_needs_rehash_flags_legacy_and_low_iteration_hashes():
    assert security.needs_rehash(None)
    assert security.needs_rehash("plain-sha256-hex")
    assert security.needs_rehash("pbkdf2_sha256$1000$salt$digest")
    assert not security.needs_rehash(security.hash_password("x"))


def test_password_problem_enforces_length():
    assert security.password_problem("") is not None
    assert security.password_problem("short") is not None
    assert security.password_problem("a" * 200) is not None
    assert security.password_problem("perfectly-fine-1") is None


def test_validate_email_and_username():
    assert security.validate_email("person@example.com")
    assert not security.validate_email("not-an-email")
    assert not security.validate_email("")
    assert security.validate_username("valid_user.name-1")
    assert not security.validate_username("ab")
    assert not security.validate_username("has a space")


def test_login_throttle_locks_out_after_max_attempts():
    security.reset_login_throttle()
    now = time.time()
    for _ in range(security.MAX_LOGIN_ATTEMPTS):
        security.record_failed_login("someone", now=now)
    assert security.lockout_remaining("someone", now=now) > 0


def test_login_throttle_resets_after_window_and_on_success():
    security.reset_login_throttle()
    now = time.time()
    for _ in range(security.MAX_LOGIN_ATTEMPTS):
        security.record_failed_login("someone", now=now)
    later = now + security.LOGIN_LOCKOUT_SECONDS + 1
    assert security.lockout_remaining("someone", now=later) == 0

    security.record_failed_login("someone-else", now=now)
    security.clear_failed_logins("someone-else")
    assert security.lockout_remaining("someone-else", now=now) == 0


def test_login_throttle_is_case_insensitive_on_username():
    security.reset_login_throttle()
    now = time.time()
    for _ in range(security.MAX_LOGIN_ATTEMPTS):
        security.record_failed_login("Someone", now=now)
    assert security.lockout_remaining("someone", now=now) > 0
