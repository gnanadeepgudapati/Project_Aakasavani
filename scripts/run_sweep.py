"""ARCHITECTURE.md §10 - the 03:00 TTL sweep cron entrypoint. Rule 5: strip
`seen`'s text after 30 days, keep the hash forever. No network at all -
this is a pure SQL sweep. plans/25-entrypoints-and-live-test.md step 25.
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
from app.jobs.sweep import sweep_expired_seen  # noqa: E402

DEFAULT_DB_PATH = Path(os.environ.get("AAKASAVANI_DB_PATH", str(REPO_ROOT / "aakasavani.db")))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the daily TTL sweep (ARCHITECTURE.md §10, Rule 5).")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to the SQLite DB (default: %(default)s)")
    args = parser.parse_args(argv)

    print(f"[run_sweep] db: {args.db}")
    conn = db_module.connect(args.db)
    try:
        db_module.migrate(conn)
        swept = sweep_expired_seen(conn, now=clock.now())
        print(f"[run_sweep] {swept} row(s) swept (text stripped, hash kept)")
        return 0
    except Exception as exc:
        print(f"[run_sweep] SWEEP FAILED: {exc!r}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
