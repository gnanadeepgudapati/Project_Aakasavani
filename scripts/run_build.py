"""ARCHITECTURE.md §8 step 07 / EDITION-AND-UI.md §1.2, run for real via
cron. plans/00b-real-data-and-ui-plan.md / plans/25-entrypoints-and-live-
test.md step 25 - the 04:00 cron entrypoint (ARCHITECTURE.md §10).

Wraps sync_feeds_to_db() -> run_build() behind a CLI. Honest stdout
progress, never silent, per CLAUDE.md's working style. A per-FEED failure
(step 23, D-2) never aborts the build and never produces a non-zero exit
here - only something genuinely outside that (a DB open failure, an
unhandled exception in selection/prefetch/swap) does.

fetch_fn/fetcher are accepted only so tests/test_scripts.py can inject
fixture-only doubles - ARCHITECTURE.md §12.2, tests never touch the
network. Real cron invocation never passes them, so run_build()'s real
defaults (app.net.fetcher._default_feed_fetch, default_fetcher()) are what
actually runs.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app import db as db_module  # noqa: E402
from app.edition.build import run_build  # noqa: E402
from app.registry import sync_feeds_to_db  # noqa: E402

# Matches app/web/deps.py's DEFAULT_DB_PATH convention, so cron and the web
# app agree on which file is "the" database without either importing the
# other.
DEFAULT_DB_PATH = Path(os.environ.get("AAKASAVANI_DB_PATH", str(REPO_ROOT / "aakasavani.db")))


def main(argv=None, *, fetch_fn=None, fetcher=None) -> int:
    parser = argparse.ArgumentParser(description="Run the 04:00 edition build (ARCHITECTURE.md §8 step 07).")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to the SQLite DB (default: %(default)s)")
    args = parser.parse_args(argv)

    print(f"[run_build] db: {args.db}")
    conn = db_module.connect(args.db)
    try:
        applied = db_module.migrate(conn)
        if applied:
            print(f"[run_build] applied migrations: {applied}")

        sync_result = sync_feeds_to_db(conn)
        print(f"[run_build] feed registry synced: {sync_result['inserted']} new, {sync_result['updated']} updated")

        enabled_count = conn.execute("SELECT COUNT(*) FROM feeds WHERE enabled = 1").fetchone()[0]
        print(f"[run_build] polling {enabled_count} enabled feed(s)...")

        edition_id = run_build(conn, fetch_fn=fetch_fn, fetcher=fetcher)

        edition = conn.execute(
            "SELECT edition_date, article_count, read_minutes, status FROM editions WHERE id = ?",
            (edition_id,),
        ).fetchone()
        failed = conn.execute(
            "SELECT name, url, fail_count, enabled FROM feeds WHERE fail_count > 0 ORDER BY fail_count DESC"
        ).fetchall()

        print(
            f"[run_build] edition {edition_id} ({edition['edition_date']}) is {edition['status']}: "
            f"{edition['article_count']} article(s), read_minutes={edition['read_minutes']}"
        )
        if failed:
            print(f"[run_build] {len(failed)} feed(s) had failures this run:")
            for f in failed:
                state = "DISABLED" if not f["enabled"] else "still enabled"
                print(f"    - {f['name']}: fail_count={f['fail_count']} ({state}) {f['url']}")
        print("[run_build] done.")
        return 0
    except Exception as exc:
        print(f"[run_build] BUILD FAILED: {exc!r}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
