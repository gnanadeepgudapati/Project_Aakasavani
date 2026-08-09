"""MANUAL ONLY. The real-network exception.

ARCHITECTURE.md §12.2, plans/00-implementation-plan.md §1 (named this file
"MANUAL ONLY. Never in the verify chain" and it was never written until
plans/25-entrypoints-and-live-test.md step 25).

NEVER runs as part of the default `pytest` invocation - excluded via
pyproject.toml's `addopts = "... --ignore=tests/test_live.py"`. Run by
hand, and ONLY by hand, with:

    pytest tests/test_live.py --noconftest -v

    (or equivalently: python tests/test_live.py)

`--noconftest` is required: tests/conftest.py's autouse `_no_network`
fixture (ARCHITECTURE.md §12.2) blocks every non-loopback socket connection
for every other test in this suite, on purpose. This file is the one
deliberate exception and must not inherit that guard - it builds its own
throwaway DB and imports nothing from conftest.py, by design.

Hits the real internet. Polls exactly ONE real feed from data/feeds.yaml
and extracts exactly ONE real article - this is the test that would have
caught D-1..D-6 (logs/SESSIONS.md, plans/00b-real-data-and-ui-plan.md):
sync_feeds_to_db() actually populating `feeds`, poll_all_feeds() actually
inserting real `seen` rows from a real HTTP response (conditional GET
headers included), the real default_fetcher() actually extracting real
article text through Trafilatura, and a real domain's robots.txt actually
being consulted before that fetch.

Rule 8 applies in FULL here - same shared limiter, same honest User-Agent,
same 1 req/sec/domain - this script is not exempt from politeness just
because it's manual and runs rarely.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from app import db as db_module
from app.edition.build import poll_all_feeds
from app.net.fetcher import default_fetcher
from app.registry import load_feeds, sync_feeds_to_db


def test_live_poll_one_real_feed_and_extract_one_real_article():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "live_test.db"
        conn = db_module.connect(db_path)
        db_module.migrate(conn)

        sync_result = sync_feeds_to_db(conn)
        print(f"[test_live] registry synced: {sync_result}")
        assert sync_result["inserted"] == 35, "sync_feeds_to_db must populate all 35 frozen feeds"

        # Pick a feed the step-01 audit already recorded as reachable,
        # rather than guessing - BLOCKED.md B-004 documents 7 known-dead
        # feeds, and this test must not depend on which 28 happen to be up
        # today staying exactly the same 28.
        feeds = load_feeds()
        reachable = [f for f in feeds if f.get("_audit_status") == "ok"]
        assert reachable, "no feed in data/feeds.yaml is marked reachable - re-run scripts/audit_feeds.py"
        target = reachable[0]
        print(f"[test_live] target feed: {target['name']} ({target['url']})")

        conn.execute("UPDATE feeds SET enabled = 0 WHERE url != ?", (target["url"],))
        conn.commit()

        inserted = poll_all_feeds(conn)  # NO fetch_fn - the real default, real network
        print(f"[test_live] poll_all_feeds inserted {inserted} row(s)")
        assert inserted > 0, f"a real poll of {target['url']} inserted zero rows"

        feed_row = conn.execute("SELECT etag, last_modified, fail_count FROM feeds WHERE url = ?", (target["url"],)).fetchone()
        print(f"[test_live] post-poll feed state: {dict(feed_row)}")
        assert feed_row["fail_count"] == 0, "a successful real poll must reset fail_count"

        row = conn.execute(
            "SELECT canonical_url FROM seen ORDER BY first_seen DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        print(f"[test_live] extracting: {row['canonical_url']}")

        fetcher = default_fetcher()  # real Fetcher, real RobotsCache, real limiter
        result = fetcher.get_full_text(row["canonical_url"])
        print(f"[test_live] fetched_via={result.fetched_via!r} reason={result.reason!r} "
              f"text_len={len(result.text) if result.text else 0}")

        assert result.fetched_via in ("live", "wayback", None), (
            f"unexpected fetched_via: {result.fetched_via!r}"
        )
        if result.text is not None:
            assert len(result.text) >= 500, "an extraction that 'succeeded' must clear the Rule-defined floor"
            assert result.fetched_via in ("live", "wayback")
        else:
            # A failure is an honest, valid outcome for ONE real article on
            # ONE real run (robots disallow, 403, paywall, etc.) - what
            # matters is that it FAILED THE RIGHT WAY: a recorded reason,
            # never a raised exception escaping this call.
            assert result.reason in (
                "robots_disallow", "wayback_backoff", "wayback_429", "total_failure",
            ), f"a failed fetch must record a known reason, got {result.reason!r}"

        conn.close()


if __name__ == "__main__":
    test_live_poll_one_real_feed_and_extract_one_real_article()
    print("tests/test_live.py: OK")
