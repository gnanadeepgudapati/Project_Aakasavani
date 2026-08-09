"""Saved FTS5 queries, not stored tags. EDITION-AND-UI.md §2.2 - the whole
argument for this shape is that a new topic is retroactive (matches history
instantly) and user-editable (edit one string, no retraining).
"""

from __future__ import annotations

import sqlite3


def add_topic(conn: sqlite3.Connection, name: str, query: str) -> int:
    cur = conn.execute(
        "INSERT INTO topics (name, query, enabled) VALUES (?, ?, 1)", (name, query)
    )
    conn.commit()
    return cur.lastrowid


def update_topic_query(conn: sqlite3.Connection, name: str, new_query: str) -> None:
    conn.execute("UPDATE topics SET query = ? WHERE name = ?", (new_query, name))
    conn.commit()


def set_topic_enabled(conn: sqlite3.Connection, name: str, enabled: bool) -> None:
    conn.execute("UPDATE topics SET enabled = ? WHERE name = ?", (int(enabled), name))
    conn.commit()


def list_topics(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM topics ORDER BY name").fetchall()


def match_topic(conn: sqlite3.Connection, name: str) -> list[sqlite3.Row]:
    """EDITION-AND-UI.md §2.2's own example query, parameterised by topic
    name instead of hardcoded to one topic."""
    topic = conn.execute("SELECT query FROM topics WHERE name = ?", (name,)).fetchone()
    if topic is None:
        raise KeyError(f"no such topic: {name}")

    return conn.execute(
        "SELECT s.* FROM seen s "
        "JOIN seen_fts f ON f.rowid = s.rowid "
        "WHERE seen_fts MATCH ? AND s.expired = 0 "
        "ORDER BY s.published_at DESC",
        (topic["query"],),
    ).fetchall()
