"""Internet Archive Save Page Now queue. ARCHITECTURE.md §2.6, §4 Flow B/C;
SOURCES.md §4 (6 captures/min, 7 concurrent sessions - we use 6/min serial,
well inside the limit).

Fully asynchronous by construction, not by convention: enqueue() is a single
fast INSERT, called from the read/build path. drain_queue() - the only thing
that ever calls save_fn (the slow, 10-60s network operation) - is a separate
function, meant to be run by a background worker, never from inside a
request handler.
"""

from __future__ import annotations

import sqlite3

from app import clock

MAX_ATTEMPTS = 3
RATE_PER_MINUTE = 6
MIN_INTERVAL_SECONDS = 60.0 / RATE_PER_MINUTE  # 10s between captures


def enqueue(conn: sqlite3.Connection, url_hash: bytes, url: str) -> bool:
    """Fast, single INSERT - safe to call from a request handler or the
    build job. Returns False if already queued (idempotent)."""
    existing = conn.execute(
        "SELECT 1 FROM ia_queue WHERE url_hash = ?", (url_hash,)
    ).fetchone()
    if existing is not None:
        return False
    conn.execute(
        "INSERT INTO ia_queue (url_hash, url, queued_at, attempts, done) "
        "VALUES (?, ?, ?, 0, 0)",
        (url_hash, url, int(clock.now().timestamp())),
    )
    conn.commit()
    return True


def enqueue_front_page(conn: sqlite3.Connection, selection: dict) -> int:
    """EDITION-AND-UI.md §1.2, 04:30: queue every edition article."""
    count = 0
    for rows in selection.values():
        for row in rows:
            if enqueue(conn, row["url_hash"], row["canonical_url"]):
                count += 1
    return count


def drain_queue(conn: sqlite3.Connection, save_fn, *, limiter=None, max_items=None) -> int:
    """The ONLY function that calls save_fn - the slow, network-touching
    operation. Never called from enqueue() or from a request handler.

    save_fn(url) -> snapshot_url, or raises on failure.
    """
    if limiter is None:
        from app.net.limiter import SharedLimiter

        limiter = SharedLimiter(min_interval_seconds=MIN_INTERVAL_SECONDS)

    pending = conn.execute(
        "SELECT * FROM ia_queue WHERE done = 0 AND attempts < ? ORDER BY queued_at ASC",
        (MAX_ATTEMPTS,),
    ).fetchall()
    if max_items is not None:
        pending = pending[:max_items]

    processed = 0
    for item in pending:
        limiter.acquire("archive.org")
        now = int(clock.now().timestamp())
        try:
            snapshot_url = save_fn(item["url"])
        except Exception:
            attempts = item["attempts"] + 1
            done = 1 if attempts >= MAX_ATTEMPTS else 0
            conn.execute(
                "UPDATE ia_queue SET attempts = ?, done = ?, last_attempt_at = ? "
                "WHERE url_hash = ?",
                (attempts, done, now, item["url_hash"]),
            )
            conn.commit()
            continue

        conn.execute(
            "UPDATE ia_queue SET done = 1, last_attempt_at = ? WHERE url_hash = ?",
            (now, item["url_hash"]),
        )
        conn.execute(
            "UPDATE read SET ia_snapshot = ? WHERE url_hash = ?",
            (snapshot_url, item["url_hash"]),
        )
        conn.commit()
        processed += 1

    return processed
