"""Nightly backup. ARCHITECTURE.md §10: "Use .backup, not cp - it handles an
in-flight write correctly." `read` is the only irreplaceable data; everything
else can be re-fetched from the internet.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def backup_db(source_conn: sqlite3.Connection, dest_path: Path | str) -> None:
    dest_conn = sqlite3.connect(str(dest_path))
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
