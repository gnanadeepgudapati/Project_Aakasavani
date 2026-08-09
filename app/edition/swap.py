"""EDITION-AND-UI.md §1.4: the atomic swap. Rule 7 - never show an empty page.

Build into 'building', flip to 'live' only on success, in one transaction.
A failure anywhere in this function leaves the previously-live edition
untouched - see test_rules.py::test_swap_is_atomic.
"""

from __future__ import annotations

import sqlite3

from app import clock


def _write_edition_items(conn: sqlite3.Connection, edition_id: int, items: list[dict]) -> None:
    for item in items:
        conn.execute(
            "INSERT INTO edition_items (edition_id, url_hash, section, rank_position) "
            "VALUES (?, ?, ?, ?)",
            (edition_id, item["url_hash"], item["section"], item["rank_position"]),
        )


def atomic_swap(
    conn: sqlite3.Connection,
    *,
    edition_date: str,
    items: list[dict],
    article_count: int | None = None,
    read_minutes: int | None = None,
) -> int:
    """items: [{"url_hash": bytes, "section": str, "rank_position": int}, ...]
    Returns the new edition's id. Raises and leaves the DB exactly as it was
    before this call if anything fails - callers must not catch and continue."""
    article_count = article_count if article_count is not None else len(items)

    try:
        cur = conn.execute(
            "INSERT INTO editions (edition_date, built_at, status, article_count, read_minutes) "
            "VALUES (?, ?, 'building', ?, ?)",
            (edition_date, int(clock.now().timestamp()), article_count, read_minutes),
        )
        edition_id = cur.lastrowid

        _write_edition_items(conn, edition_id, items)

        conn.execute(
            "UPDATE editions SET status = 'superseded' WHERE status = 'live' AND id != ?",
            (edition_id,),
        )
        conn.execute("UPDATE editions SET status = 'live' WHERE id = ?", (edition_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return edition_id
