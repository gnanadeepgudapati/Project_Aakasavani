"""Step 12 acceptance tests. REQUIREMENTS.md R-069..R-071."""

from datetime import datetime, timedelta, timezone

from app.jobs.backup import backup_db
from app.jobs.sweep import sweep_expired_seen


def test_sweep_strips_keeps_hash(db_conn, frozen_clock):
    """R-069. Job-level (vs. R-008's unit-level rule-test assertion)."""
    expired_at = int(frozen_clock.now().timestamp()) - 1
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, full_text, fetched_via, first_seen, "
        "expires_at, expired) VALUES "
        "(?, 'https://x.test/a', 'T', 'S', 'tech', 1, 'D', 'body', 'live', 1, ?, 0)",
        (b"\x50" * 32, expired_at),
    )
    db_conn.commit()

    swept = sweep_expired_seen(db_conn, now=frozen_clock.now())
    assert swept == 1

    row = db_conn.execute(
        "SELECT title, description, source, full_text, fetched_via, expired, url_hash "
        "FROM seen WHERE url_hash = ?",
        (b"\x50" * 32,),
    ).fetchone()
    assert row["title"] is None
    assert row["description"] is None
    assert row["source"] is None
    assert row["full_text"] is None
    assert row["fetched_via"] is None
    assert row["expired"] == 1
    assert row["url_hash"] == b"\x50" * 32  # the hash survives, permanently


def test_sweep_idempotent(db_conn, frozen_clock):
    """R-070."""
    expired_at = int(frozen_clock.now().timestamp()) - 1
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, section, first_seen, expires_at) "
        "VALUES (?, 'https://x.test/b', 'tech', 1, ?)",
        (b"\x51" * 32, expired_at),
    )
    db_conn.commit()

    first = sweep_expired_seen(db_conn, now=frozen_clock.now())
    second = sweep_expired_seen(db_conn, now=frozen_clock.now())

    assert first == 1
    assert second == 0, "running the sweep twice must not re-touch already-swept rows"


def test_backup_is_readable(db_conn, tmp_path):
    """R-071. Uses the sqlite3 .backup() API, not the CLI - CLAUDE.md prompt
    R-2: dev is Windows, prod is Ubuntu; the sqlite3 CLI may not exist
    locally, so backup must go through the Python API, which works
    everywhere Python's sqlite3 module does."""
    db_conn.execute(
        "INSERT INTO read (url_hash, canonical_url, title, source, "
        "published_at, full_text, fetched_via, read_at) VALUES "
        "(?, 'https://x.test/c', 'Backed Up Title', 'S', 1, 'body text', 'feed', 1)",
        (b"\x52" * 32,),
    )
    db_conn.commit()

    backup_path = tmp_path / "backup.db"
    backup_db(db_conn, backup_path)

    assert backup_path.exists()

    import sqlite3

    check_conn = sqlite3.connect(str(backup_path))
    check_conn.row_factory = sqlite3.Row
    row = check_conn.execute(
        "SELECT title, full_text FROM read WHERE url_hash = ?", (b"\x52" * 32,)
    ).fetchone()
    check_conn.close()

    assert row is not None
    assert row["title"] == "Backed Up Title"
    assert row["full_text"] == "body text"
