"""EDITION-AND-UI.md §1.2/§1.5 / ARCHITECTURE.md §10 - the :30 top-up cron
entrypoint, every 30 min from 05:00. plans/25-entrypoints-and-live-test.md
step 25.

Wraps sync_feeds_to_db() -> run_topup() behind a CLI. Headlines only - never
rebuilds the edition (app/jobs/topup.py's whole point; see R-086/R-087).

fetch_fn is accepted only so tests/test_scripts.py can inject a
fixture-only double - ARCHITECTURE.md §12.2, tests never touch the network.
Real cron invocation never passes it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app import db as db_module  # noqa: E402
from app.jobs.topup import run_topup  # noqa: E402
from app.registry import sync_feeds_to_db  # noqa: E402

DEFAULT_DB_PATH = Path(os.environ.get("AAKASAVANI_DB_PATH", str(REPO_ROOT / "aakasavani.db")))


def main(argv=None, *, fetch_fn=None) -> int:
    parser = argparse.ArgumentParser(description="Run a headlines-only top-up poll (EDITION-AND-UI.md §1.5).")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to the SQLite DB (default: %(default)s)")
    args = parser.parse_args(argv)

    print(f"[run_topup] db: {args.db}")
    conn = db_module.connect(args.db)
    try:
        db_module.migrate(conn)

        sync_result = sync_feeds_to_db(conn)
        print(f"[run_topup] feed registry synced: {sync_result['inserted']} new, {sync_result['updated']} updated")

        inserted = run_topup(conn, fetch_fn=fetch_fn)
        print(f"[run_topup] {inserted} new headline(s) added")
        return 0
    except Exception as exc:
        print(f"[run_topup] TOP-UP FAILED: {exc!r}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
