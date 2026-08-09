"""Daily TTL sweep. ARCHITECTURE.md §10, Rule 5: strip text, keep the hash
forever. Includes seen.full_text/fetched_via - migration 002, S-007.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime


def sweep_expired_seen(conn: sqlite3.Connection, now: datetime) -> int:
    """Returns how many rows were swept this call."""
    now_ts = int(now.timestamp())
    cur = conn.execute(
        "UPDATE seen SET title = NULL, description = NULL, source = NULL, "
        "full_text = NULL, fetched_via = NULL, expired = 1 "
        "WHERE expires_at < ? AND expired = 0",
        (now_ts,),
    )
    conn.commit()
    return cur.rowcount
