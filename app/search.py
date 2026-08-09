"""ARCHITECTURE.md §1: "FTS5 SEARCH over your reads." Personal reading
history only - Rule 2/5's boundary matters here too: `seen` is the
unread firehose, `read` is what you actually opened. Search must never
reach into the firehose.
"""

from __future__ import annotations

import sqlite3


def search_read(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    # An empty/blank query has no meaningful match and FTS5's MATCH raises
    # sqlite3.OperationalError on '' - fail soft to no results, not a 500.
    if not query or not query.strip():
        return []
    return conn.execute(
        "SELECT r.* FROM read r "
        "JOIN read_fts f ON f.rowid = r.rowid "
        "WHERE read_fts MATCH ? "
        "ORDER BY r.read_at DESC",
        (query,),
    ).fetchall()
