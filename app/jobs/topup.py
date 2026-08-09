"""EDITION-AND-UI.md §1.2/§1.5: every 30 min from 05:00, headlines only -
adds new `seen` rows via the same poll/parse/dedupe path the build uses, but
never selects a front page and never swaps an edition. Just a thinner slice
of run_build(), reused rather than duplicated.
"""

from __future__ import annotations

import sqlite3

from app.edition.build import poll_all_feeds


def run_topup(conn: sqlite3.Connection, fetch_fn=None) -> int:
    """Returns how many new seen rows were inserted. Structurally cannot
    rebuild the edition - it calls nothing from app.edition.select or
    app.edition.swap."""
    return poll_all_feeds(conn, fetch_fn=fetch_fn)
