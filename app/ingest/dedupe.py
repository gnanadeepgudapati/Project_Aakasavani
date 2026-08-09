"""Rule 2: URL dedup, never story dedup - the same event from six outlets
yields six rows, deliberately. ARCHITECTURE.md §2.2, §4 Flow A.
"""

from __future__ import annotations

import sqlite3

from app import clock

TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days - ARCHITECTURE.md §10


def insert_if_new(
    conn: sqlite3.Connection,
    *,
    url_hash: bytes,
    canonical_url: str,
    title: str,
    source: str,
    section: str,
    published_at: int | None,
    description: str,
    image_url: str | None = None,
    feed_id: int | None = None,
) -> bool:
    """Returns True if a new row was inserted, False if url_hash already
    existed in `seen` (i.e. this URL was already seen - skip it, per Rule 2's
    URL-level, not story-level, dedup)."""
    existing = conn.execute(
        "SELECT 1 FROM seen WHERE url_hash = ?", (url_hash,)
    ).fetchone()
    if existing is not None:
        return False

    now = int(clock.now().timestamp())
    conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, feed_id, "
        "published_at, description, image_url, section, first_seen, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            url_hash, canonical_url, title, source, feed_id,
            published_at, description, image_url, section,
            now, now + TTL_SECONDS,
        ),
    )
    conn.commit()
    return True
