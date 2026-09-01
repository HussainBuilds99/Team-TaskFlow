"""Configuration constants and runtime paths for Team TaskFlow.

Paths are resolved through functions rather than module level constants so that
tests (and alternative deployments) can point the app at a different database by
setting ``TASKFLOW_DB_PATH`` / ``TASKFLOW_UPLOAD_DIR`` before the first call.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Team TaskFlow"
APP_ICON = "🗂️"
APP_TAGLINE = "Collaborative task management for students, clubs, and teams."

# Task vocabulary -----------------------------------------------------------
STATUS_OPTIONS = ["Pending", "In Progress", "Completed"]
# Archiving is stored in its own column; the label is kept for display and for
# migrating databases created by older versions that wrote it into `status`.
ARCHIVE_STATUS = "Archived"
PRIORITY_OPTIONS = ["High", "Medium", "Low"]
CATEGORY_OPTIONS = [
    "Assignment",
    "Meeting",
    "Presentation",
    "Research",
    "Personal",
    "Other",
]
RECURRENCE_OPTIONS = ["None", "Daily", "Weekly", "Monthly"]
RECURRING_VALUES = frozenset({"Daily", "Weekly", "Monthly"})
SORT_OPTIONS = ["Due Date", "Priority", "Status", "Progress", "Title"]

DEFAULT_CATEGORY = "Other"
DEFAULT_PRIORITY = "Medium"
DEFAULT_STATUS = "Pending"
DEFAULT_RECURRENCE = "None"

# Validation limits ---------------------------------------------------------
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MIN_TITLE_LENGTH = 3
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_COMMENT_LENGTH = 2000
MAX_SUBTASK_LENGTH = 200
MAX_NAME_LENGTH = 100
MAX_TAGS = 12
MAX_TAG_LENGTH = 24
MAX_CSV_ROWS = 1000
MAX_PRESET_NAME_LENGTH = 60

# Security ------------------------------------------------------------------
PBKDF2_ITERATIONS = 240_000
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300

# Attachments ---------------------------------------------------------------
ALLOWED_ATTACHMENT_EXTENSIONS = frozenset(
    {".txt", ".pdf", ".png", ".jpg", ".jpeg", ".csv", ".docx", ".pptx", ".xlsx"}
)
MAX_ATTACHMENT_SIZE_MB = 10
MAX_ATTACHMENT_SIZE_BYTES = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024

# Theming -------------------------------------------------------------------
THEME_OPTIONS = ["Ocean Slate", "Midnight Indigo", "Warm Ember"]
LEGACY_THEME_MAP = {
    "Aurora Glass": "Ocean Slate",
    "Cyber Neon": "Midnight Indigo",
    "Sunset Pulse": "Warm Ember",
}

_DEFAULT_DB_PATH = "taskmanager.db"
_DEFAULT_UPLOAD_DIR = "task_uploads"


def db_path() -> Path:
    """Location of the SQLite database file, used when ``database_url()`` is unset."""
    return Path(os.environ.get("TASKFLOW_DB_PATH", _DEFAULT_DB_PATH))


def upload_dir() -> Path:
    """Directory that stores uploaded task attachments."""
    return Path(os.environ.get("TASKFLOW_UPLOAD_DIR", _DEFAULT_UPLOAD_DIR))


def database_url() -> str | None:
    """A SQLAlchemy connection URL for a hosted database, or ``None`` for SQLite.

    Set the ``DATABASE_URL`` environment variable (e.g. from a free Postgres
    host like Neon or Supabase) so accounts and tasks persist across restarts
    and redeploys - without it, the app falls back to a local SQLite file that
    most hosting platforms wipe whenever they restart the container.

    Connection strings that start with ``postgres://`` or plain
    ``postgresql://`` (the format most hosts hand out) are normalised to use
    the ``psycopg`` driver this app ships with, so a copy-pasted URL works
    without edits.
    """
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        return None
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw
