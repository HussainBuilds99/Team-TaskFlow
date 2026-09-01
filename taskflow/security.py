"""Password hashing, input validation and brute-force throttling."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
import time

from .config import (
    LOGIN_LOCKOUT_SECONDS,
    MAX_LOGIN_ATTEMPTS,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PBKDF2_ITERATIONS,
)

_PBKDF2_PREFIX = "pbkdf2_sha256$"
_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]{3,30}")


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a fresh random salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    ).hex()
    return f"{_PBKDF2_PREFIX}{PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    """Check a password against a stored hash, tolerating legacy sha256 hashes."""
    if not stored_hash or password is None:
        return False
    if stored_hash.startswith(_PBKDF2_PREFIX):
        try:
            _, rounds, salt, digest = stored_hash.split("$", maxsplit=3)
            calculated = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(rounds)
            ).hex()
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(calculated, digest)
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, stored_hash)


def needs_rehash(stored_hash: str | None) -> bool:
    """True when a stored hash uses an outdated scheme or iteration count."""
    if not stored_hash or not stored_hash.startswith(_PBKDF2_PREFIX):
        return True
    try:
        rounds = int(stored_hash.split("$", maxsplit=2)[1])
    except (IndexError, ValueError):
        return True
    return rounds < PBKDF2_ITERATIONS


def validate_email(email) -> bool:
    """True when the value looks like a usable email address."""
    return bool(email) and bool(_EMAIL_PATTERN.fullmatch(str(email).strip()))


def validate_username(username) -> bool:
    """True when the username is 3-30 chars of letters, digits, ``_``, ``.`` or ``-``."""
    return bool(username) and bool(_USERNAME_PATTERN.fullmatch(str(username).strip()))


def password_problem(password) -> str | None:
    """Return a human readable reason a password is unacceptable, else ``None``."""
    if not password:
        return "Password is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters long."
    if password.strip() != password:
        return "Password cannot start or end with a space."
    return None


# --- Login throttling ------------------------------------------------------
# Streamlit serves every browser session from one process, so an in-memory
# counter is enough to slow down password guessing against a single account.

_lock = threading.Lock()
_failed_logins: dict[str, tuple[int, float]] = {}


def _key(username) -> str:
    return str(username or "").strip().lower()


def lockout_remaining(username, now: float | None = None) -> int:
    """Seconds left before ``username`` may attempt a login again (0 when free)."""
    reference = time.time() if now is None else now
    with _lock:
        attempts, last_attempt = _failed_logins.get(_key(username), (0, 0.0))
    if attempts < MAX_LOGIN_ATTEMPTS:
        return 0
    remaining = LOGIN_LOCKOUT_SECONDS - (reference - last_attempt)
    return max(0, int(remaining))


def record_failed_login(username, now: float | None = None) -> None:
    """Count a failed attempt, restarting the window once a lockout expires."""
    reference = time.time() if now is None else now
    key = _key(username)
    with _lock:
        attempts, last_attempt = _failed_logins.get(key, (0, 0.0))
        if attempts >= MAX_LOGIN_ATTEMPTS and reference - last_attempt >= LOGIN_LOCKOUT_SECONDS:
            attempts = 0
        _failed_logins[key] = (attempts + 1, reference)


def clear_failed_logins(username) -> None:
    """Forget failed attempts after a successful login."""
    with _lock:
        _failed_logins.pop(_key(username), None)


def reset_login_throttle() -> None:
    """Clear all throttling state (used by tests)."""
    with _lock:
        _failed_logins.clear()
