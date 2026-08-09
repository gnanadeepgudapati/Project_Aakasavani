"""Front-page selection. EDITION-AND-UI.md "Selection - front page ranking",
as amended by S-003 (13/section, not 8) and S-001 (3 sections).

"Start deliberately dumb": recency, tie-broken by a hand-written source
weight. No engagement modelling, no scoring function.
"""

from __future__ import annotations

import sqlite3

from app.config import SECTIONS

PER_SECTION = 13  # logs/SESSIONS.md S-003: 13 x 3 sections ~= 40


def select_edition(conn: sqlite3.Connection, per_section: int = PER_SECTION) -> dict[str, list[sqlite3.Row]]:
    """Returns {section: [rows]}, each ordered by published_at DESC, tied
    broken by feeds.source_weight DESC, capped at per_section."""
    result: dict[str, list[sqlite3.Row]] = {}
    for section in SECTIONS:
        rows = conn.execute(
            "SELECT s.*, COALESCE(f.source_weight, 3) AS weight "
            "FROM seen s LEFT JOIN feeds f ON s.feed_id = f.id "
            "WHERE s.section = ? AND s.expired = 0 "
            "ORDER BY s.published_at DESC, weight DESC "
            "LIMIT ?",
            (section, per_section),
        ).fetchall()
        result[section] = rows
    return result
