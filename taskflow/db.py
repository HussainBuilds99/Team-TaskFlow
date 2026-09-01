"""Database connection handling, schema creation and migrations.

Runs on SQLite by default (zero setup, good for local development and tests)
or on Postgres when ``DATABASE_URL`` is set (see :func:`taskflow.config.database_url`) -
the same query code works against both through SQLAlchemy's Core engine.
"""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from . import config

# Every query in this codebase is written with SQLite-style ``?`` placeholders;
# _translate() below rewrites them into SQLAlchemy's ``:name`` style so the same
# call sites work unchanged against Postgres too.
_PLACEHOLDER_RE = re.compile(r"\?")

_lock = threading.RLock()
_engine: Engine | None = None
_initialised = False


def _build_engine() -> Engine:
    url = config.database_url()
    if url:
        return create_engine(url, pool_pre_ping=True, future=True)

    parent = config.db_path().parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{config.db_path()}",
        connect_args={"check_same_thread": False},
        future=True,
    )


def get_engine() -> Engine:
    """The process-wide SQLAlchemy engine, built lazily from current config."""
    global _engine
    with _lock:
        if _engine is None:
            _engine = _build_engine()
        return _engine


def is_postgres() -> bool:
    return get_engine().dialect.name == "postgresql"


def _translate(sql: str, params):
    """Turn ``?`` placeholders and a positional tuple into a bound ``text()`` statement."""
    params = tuple(params or ())
    counter = {"i": 0}

    def _replace(_match):
        counter["i"] += 1
        return f":p{counter['i'] - 1}"

    translated = _PLACEHOLDER_RE.sub(_replace, sql)
    bind = {f"p{i}": value for i, value in enumerate(params)}
    return text(translated), bind


@contextmanager
def connect():
    """Yield a connection that commits on success and rolls back on error.

    A connection per operation keeps things simple under Streamlit's per-session
    threads; SQLAlchemy's pool handles reuse underneath. SQLAlchemy 2.x
    "autobegins" a transaction on the first statement, so there is no explicit
    ``connection.begin()`` here - it would conflict with that.
    """
    engine = get_engine()
    connection = engine.connect()
    try:
        if engine.dialect.name != "postgresql":
            connection.execute(text("PRAGMA foreign_keys = ON"))
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fetch_all(sql: str, params: tuple | list = ()) -> list[dict]:
    """Run a query and return the rows as plain dictionaries."""
    statement, bind = _translate(sql, params)
    with connect() as connection:
        rows = connection.execute(statement, bind).mappings().all()
    return [dict(row) for row in rows]


def fetch_one(sql: str, params: tuple | list = ()) -> dict | None:
    """Run a query and return the first row as a dictionary, if any."""
    statement, bind = _translate(sql, params)
    with connect() as connection:
        row = connection.execute(statement, bind).mappings().first()
    return dict(row) if row else None


def execute(sql: str, params: tuple | list = ()) -> int:
    """Run a statement and return the number of affected rows."""
    statement, bind = _translate(sql, params)
    with connect() as connection:
        result = connection.execute(statement, bind)
        return result.rowcount


def execute_returning_id(sql: str, params: tuple | list = ()) -> int:
    """Run an INSERT and return the new row's id, on either SQLite or Postgres.

    SQLite exposes the last inserted id on the cursor; Postgres has no such
    concept and needs an explicit ``RETURNING id`` clause instead.
    """
    statement, bind = _translate(sql, params)
    with connect() as connection:
        if is_postgres():
            returning = text(statement.text.rstrip().rstrip(";") + " RETURNING id")
            return connection.execute(returning, bind).scalar_one()
        return connection.execute(statement, bind).lastrowid


def list_tables() -> set[str]:
    """Names of every user table, used by tests to sanity-check the schema."""
    engine = get_engine()
    with connect() as connection:
        if engine.dialect.name == "postgresql":
            rows = connection.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            ).all()
        else:
            rows = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            ).all()
    return {row[0] for row in rows}


def _schema_statements(dialect: str) -> tuple[str, ...]:
    pk = "id SERIAL PRIMARY KEY" if dialect == "postgresql" else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    return (
        f"""
        CREATE TABLE IF NOT EXISTS users (
            {pk},
            username TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS tasks (
            {pk},
            title TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL DEFAULT 'Other',
            creator_id INTEGER NOT NULL,
            assignee_id INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            progress INTEGER NOT NULL DEFAULT 0,
            tags TEXT DEFAULT '',
            recurrence TEXT NOT NULL DEFAULT 'None',
            last_recurrence_at TIMESTAMP,
            archived INTEGER NOT NULL DEFAULT 0,
            previous_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES users(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS subtasks (
            {pk},
            task_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS filter_presets (
            {pk},
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS task_comments (
            {pk},
            task_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS task_attachments (
            {pk},
            task_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS activity_log (
            {pk},
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
    )


_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_creator ON tasks(creator_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_archived ON tasks(archived)",
    "CREATE INDEX IF NOT EXISTS idx_subtasks_task ON subtasks(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_comments_task ON task_comments(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_attachments_task ON task_attachments(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_log_created_at ON activity_log(created_at)",
    # Username lookups are case-insensitive everywhere in taskflow.users; an
    # expression index (rather than SQLite's COLLATE NOCASE, which Postgres
    # doesn't have) keeps that fast and unique on both backends.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower ON users (LOWER(username))",
)


def _existing_columns(connection, dialect: str, table_name: str) -> set[str]:
    if dialect == "postgresql":
        rows = connection.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
            {"t": table_name},
        ).all()
        return {row[0] for row in rows}
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).all()
    return {row[1] for row in rows}


def _apply_migrations(connection, dialect: str) -> None:
    # Older releases had a `role` column on users (Admin/Member); the app is
    # now role-free, so drop it from any database created before this change.
    if "role" in _existing_columns(connection, dialect, "users"):
        connection.execute(text("ALTER TABLE users DROP COLUMN role"))


def init_db(force: bool = False) -> None:
    """Create the schema, apply migrations and ensure the upload directory.

    Safe to call on every Streamlit rerun: the work is done once per process
    unless ``force`` is set or :func:`reset_initialisation_state` was called.
    """
    global _initialised
    with _lock:
        if not force and _initialised:
            return

        engine = get_engine()
        dialect = engine.dialect.name
        config.upload_dir().mkdir(parents=True, exist_ok=True)

        with connect() as connection:
            if dialect != "postgresql":
                connection.execute(text("PRAGMA journal_mode = WAL"))
            for statement in _schema_statements(dialect):
                connection.execute(text(statement))
            _apply_migrations(connection, dialect)
            for statement in _INDEXES:
                connection.execute(text(statement))

        _initialised = True


def reset_initialisation_state() -> None:
    """Forget the current engine and schema state (used by tests)."""
    global _engine, _initialised
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _initialised = False
