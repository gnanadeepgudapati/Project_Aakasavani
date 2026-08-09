"""Connection + migration runner. Single file, single process - Rule 10.

Migrations are plain .sql files in app/migrations/, named NNN_description.sql,
applied in order, each recorded in schema_migrations so re-running migrate()
on an already-migrated DB is a no-op.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect(path: Path | str) -> sqlite3.Connection:
    # check_same_thread=False: FastAPI dispatches sync route handlers to a
    # threadpool, so a connection created on one thread (e.g. by a test's
    # db_conn fixture, or get_db()'s generator) gets USED from another.
    # Safe here - ARCHITECTURE.md §10: single writer, single reader process,
    # never truly concurrent within one request/test.
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if not exists:
        return set()
    return {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}


def migrate(conn: sqlite3.Connection) -> list[int]:
    """Applies every migration in app/migrations/ not yet recorded as
    applied. Returns the list of versions applied THIS call (empty if
    already up to date - idempotent, per R-028)."""
    applied = _applied_versions(conn)
    newly_applied = []

    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(sql_file.name.split("_", 1)[0])
        if version in applied:
            continue

        script = sql_file.read_text(encoding="utf-8")
        conn.executescript(script)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, unixepoch())",
            (version,),
        )
        conn.commit()
        newly_applied.append(version)

    return newly_applied
