# Team TaskFlow

A collaborative task manager for small teams, clubs, and classrooms, built with
[Streamlit](https://streamlit.io).

## Features

- Task creation, editing, archiving, checklists, comments and file attachments
- Kanban board, calendar view, planner, and productivity analytics
- Recurring tasks (daily/weekly/monthly), tags, saved filter presets
- Every account has equal access; a task can be edited by its creator or
  assignee, and deleted/archived by its creator
- CSV export/import and an audit trail of every action
- Three built-in visual themes

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app22.py
```

By default the app stores data in a local SQLite file (`taskmanager.db`) next
to `app22.py`. That's fine for trying things out, but most hosting platforms
(including Streamlit Community Cloud) wipe local files whenever the app
restarts or redeploys - so accounts and tasks won't survive for long unless
you point the app at a real database (see below).

### Persisting data with Postgres

Set the `DATABASE_URL` environment variable to a Postgres connection string
and the app uses it instead of SQLite - accounts and tasks then survive
restarts, redeploys, and scaling to multiple app instances.

1. Create a free Postgres database. [Neon](https://neon.tech) and
   [Supabase](https://supabase.com) both have a free tier that takes about a
   minute to set up; either gives you a connection string that looks like
   `postgres://user:password@host/dbname`.
2. Set it as `DATABASE_URL`:
   - **Locally**: `export DATABASE_URL="postgres://..."` before running
     `streamlit run app22.py`, or put it in a `.env` file your shell loads.
   - **Streamlit Community Cloud**: add it to your app's *Secrets* as
     `DATABASE_URL = "postgres://..."` (Settings → Secrets). The app reads
     Streamlit secrets automatically at startup.
   - **Any other host**: set it as a regular environment variable in the
     platform's dashboard.
3. Redeploy/restart the app. On first run it creates the schema in that
   database automatically - nothing else to run by hand.

No code changes are needed to switch backends: the same queries run against
SQLite or Postgres, and connection strings starting with `postgres://` or
`postgresql://` are normalised automatically to use the driver this app
ships with.

### Configuration reference

| Variable               | Effect                                                          |
| ----------------------- | ---------------------------------------------------------------- |
| `DATABASE_URL`          | Postgres connection string. When set, used instead of SQLite.   |
| `TASKFLOW_DB_PATH`      | SQLite file location, used only when `DATABASE_URL` is unset. Defaults to `taskmanager.db`. |
| `TASKFLOW_UPLOAD_DIR`   | Directory for uploaded attachments. Defaults to `task_uploads`. |

## Project layout

```
app22.py               Streamlit entry point (kept at the repo root for
                        compatibility with existing deployment configs)
taskflow/
  app.py                Page setup and routing between the auth and dashboard views
  config.py              Constants: option lists, limits, paths, DATABASE_URL
  db.py                   Connection handling, schema and migrations (SQLite + Postgres)
  security.py             Password hashing, validation, login throttling
  users.py                Accounts and authentication
  permissions.py          Who may edit/delete a task or attachment
  tasks.py                Task CRUD, recurrence, bulk operations, CSV import
  subtasks.py             Checklists
  comments.py              Task discussion threads
  attachments.py           File uploads, stored safely under task_uploads/
  presets.py               Saved sidebar filter combinations
  analytics.py             Filtering, sorting, reporting, CSV export (pure functions)
  activity.py               Audit log
  demo.py                    One-click sample data
  ui/                         Streamlit rendering, kept separate from the data layer
tests/                  pytest suite covering the taskflow package
```

The data layer (everything outside `taskflow/ui/`) has no dependency on
Streamlit and is fully unit tested. The `ui/` package renders that data and
contains the only `import streamlit` statements in the app.

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests run against SQLite by default. To run the same suite against Postgres
(useful before deploying), point `DATABASE_URL` at a scratch database first:

```bash
DATABASE_URL="postgres://user:password@localhost/taskflow_test" pytest
```

Each test truncates its tables before running, so the suite is safe to run
repeatedly against the same scratch database.

## Security notes

- Passwords are hashed with PBKDF2-HMAC-SHA256 (240,000 iterations) and
  rehashed automatically on next login if a weaker/legacy hash is found.
- Repeated failed logins for a username are throttled.
- All user-supplied text rendered as HTML is escaped.
- Uploaded files are restricted by extension and size, stored under
  randomised names, and read back only from inside the configured upload
  directory.
- Every task/comment/attachment mutation is checked against the acting
  user's relationship to the task (creator/assignee/uploader), both in the
  data layer and the UI.
