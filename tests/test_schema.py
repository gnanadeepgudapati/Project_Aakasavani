"""Step 04 acceptance tests. REQUIREMENTS.md R-028..R-032."""

import sqlite3

import pytest

from app import db


def test_migrations_idempotent(temp_db_path):
    """R-028."""
    conn = db.connect(temp_db_path)
    first = db.migrate(conn)
    assert first == [1]

    second = db.migrate(conn)
    assert second == [], "re-applying migrations must be a no-op"

    # sanity: schema is genuinely usable, not just "no error"
    conn.execute("SELECT COUNT(*) FROM feeds")
    conn.close()


def test_pragmas_applied(db_conn):
    """R-029."""
    mode = db_conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"

    fk = db_conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1

    timeout = db_conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout == 5000


def test_fts_stays_in_sync_on_insert_update_delete(db_conn):
    """R-030."""
    db_conn.execute(
        "INSERT INTO read (url_hash, canonical_url, title, source, "
        "published_at, full_text, fetched_via, read_at) "
        "VALUES (?, 'https://x.test/a', 'Original Title', 'Source', 1, "
        "'some body text here', 'feed', 1)",
        (b"\x10" * 32,),
    )
    db_conn.commit()

    hit = db_conn.execute(
        "SELECT rowid FROM read_fts WHERE read_fts MATCH 'Original'"
    ).fetchall()
    assert len(hit) == 1, "INSERT must be reflected in read_fts immediately"

    db_conn.execute(
        "UPDATE read SET title = 'Renamed Title' WHERE url_hash = ?", (b"\x10" * 32,)
    )
    db_conn.commit()

    stale = db_conn.execute(
        "SELECT rowid FROM read_fts WHERE read_fts MATCH 'Original'"
    ).fetchall()
    assert stale == [], "UPDATE must remove the old text from the index"
    fresh = db_conn.execute(
        "SELECT rowid FROM read_fts WHERE read_fts MATCH 'Renamed'"
    ).fetchall()
    assert len(fresh) == 1, "UPDATE must add the new text to the index"

    db_conn.execute("DELETE FROM read WHERE url_hash = ?", (b"\x10" * 32,))
    db_conn.commit()

    gone = db_conn.execute(
        "SELECT rowid FROM read_fts WHERE read_fts MATCH 'Renamed'"
    ).fetchall()
    assert gone == [], "DELETE must remove the row from the index"

    # seen_fts gets the identical treatment - one representative check
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, first_seen, expires_at) "
        "VALUES (?, 'https://x.test/b', 'Seen Headline', 'S', 'tech', 1, "
        "'a description', 1, 999999999)",
        (b"\x11" * 32,),
    )
    db_conn.commit()
    hit2 = db_conn.execute(
        "SELECT rowid FROM seen_fts WHERE seen_fts MATCH 'Headline'"
    ).fetchall()
    assert len(hit2) == 1


def test_edition_items_fk_enforced(db_conn):
    """R-031."""
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            "INSERT INTO edition_items (edition_id, url_hash, section, rank_position) "
            "VALUES (9999, ?, 'tech', 1)",
            (b"\x20" * 32,),
        )
        db_conn.commit()


def test_section_check_constraint(db_conn):
    """R-032."""
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            "INSERT INTO seen (url_hash, canonical_url, section, "
            "first_seen, expires_at) VALUES (?, 'https://x.test/c', "
            "'not_a_real_section', 1, 999999999)",
            (b"\x21" * 32,),
        )
        db_conn.commit()
