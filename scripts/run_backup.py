"""ARCHITECTURE.md §10 - the 02:30 backup cron entrypoint. `read` is the
only irreplaceable data; everything else can be re-fetched from the
internet. Uses sqlite3's own .backup (via app.jobs.backup.backup_db), not
`cp` - it handles an in-flight write correctly. No network at all.
plans/25-entrypoints-and-live-test.md step 25.

Destination naming follows ARCHITECTURE.md §10's example
(`/backups/$(date +%F).db`) - one dated file per day, IST edition-date
based (app.clock.now_ist()), not UTC, so the filename matches the edition
it was taken alongside.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app import clock  # noqa: E402
from app import db as db_module  # noqa: E402
from app.jobs.backup import backup_db  # noqa: E402

DEFAULT_DB_PATH = Path(os.environ.get("AAKASAVANI_DB_PATH", str(REPO_ROOT / "aakasavani.db")))
DEFAULT_DEST_DIR = Path(os.environ.get("AAKASAVANI_BACKUP_DIR", str(REPO_ROOT / "backups")))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Back up the SQLite DB (ARCHITECTURE.md §10).")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to the SQLite DB (default: %(default)s)")
    parser.add_argument("--dest-dir", type=Path, default=DEFAULT_DEST_DIR, help="Backup directory (default: %(default)s)")
    args = parser.parse_args(argv)

    print(f"[run_backup] db: {args.db}")
    conn = db_module.connect(args.db)
    try:
        db_module.migrate(conn)
        args.dest_dir.mkdir(parents=True, exist_ok=True)
        dest = args.dest_dir / f"{clock.now_ist().date().isoformat()}.db"

        backup_db(conn, dest)
        print(f"[run_backup] {args.db} -> {dest}")
        return 0
    except Exception as exc:
        print(f"[run_backup] BACKUP FAILED: {exc!r}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
