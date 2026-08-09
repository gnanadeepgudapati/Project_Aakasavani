"""Step 25 acceptance tests. REQUIREMENTS.md R-103..R-105.
plans/25-entrypoints-and-live-test.md.

Exercises each scripts/run_*.py entrypoint's main() against a real,
migrated temp DB, with fetch_fn/fetcher injected as fixture-only doubles -
ARCHITECTURE.md §12.2, tests never touch the network. sync_feeds_to_db()
itself only reads the real data/feeds.yaml, which is local and has no
network dependency of its own.
"""

from __future__ import annotations

from app import db as db_module
from app.net.fetcher import FeedFetchResult, FetchResult
from scripts import run_backup, run_build, run_sweep, run_topup


def _feed_xml(titles):
    entries = "".join(
        f"<item><title>{t}</title><link>https://x.test/{i}</link>"
        f"<description>D{i}</description></item>"
        for i, t in enumerate(titles)
    )
    return f"<?xml version='1.0'?><rss><channel>{entries}</channel></rss>".encode()


class _FakeFetcher:
    def get_full_text(self, url, feed_content=None):
        return FetchResult(text="prefetched body " * 50, fetched_via="live")


def test_run_build_syncs_registry_and_produces_a_live_edition(temp_db_path):
    """R-103. Also proves sync_feeds_to_db() runs before polling - the
    real 35-feed registry lands in `feeds` even though this script was
    invoked against a brand-new, empty DB."""
    def fetch_fn(url, etag, last_modified):
        return FeedFetchResult(status=200, body=_feed_xml(["A live-run headline"]))

    exit_code = run_build.main(["--db", str(temp_db_path)], fetch_fn=fetch_fn, fetcher=_FakeFetcher())
    assert exit_code == 0

    conn = db_module.connect(temp_db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0] == 35
        assert conn.execute("SELECT COUNT(*) FROM editions WHERE status='live'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0] > 0
    finally:
        conn.close()


def test_run_build_exits_nonzero_on_unhandled_failure(temp_db_path, monkeypatch):
    """R-103. A per-FEED failure must never be fatal (step 23) - but
    something genuinely outside that (simulated here) must still exit 1,
    not silently exit 0."""
    def boom(*a, **k):
        raise RuntimeError("simulated catastrophic failure")

    # Patched where run_build.py looked it up (`from app.registry import
    # sync_feeds_to_db` binds the name into scripts.run_build's own
    # namespace), not where it's defined - patching app.registry's copy
    # wouldn't affect the already-bound reference.
    monkeypatch.setattr(run_build, "sync_feeds_to_db", boom)

    exit_code = run_build.main(["--db", str(temp_db_path)])
    assert exit_code == 1


def test_run_topup_adds_headlines_without_creating_an_edition(temp_db_path):
    """R-104."""
    def fetch_fn(url, etag, last_modified):
        return FeedFetchResult(status=200, body=_feed_xml(["Top-up headline"]))

    exit_code = run_topup.main(["--db", str(temp_db_path)], fetch_fn=fetch_fn)
    assert exit_code == 0

    conn = db_module.connect(temp_db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0] == 35, "sync_feeds_to_db must run before polling"
        assert conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM editions").fetchone()[0] == 0, "top-up must never create an edition"
    finally:
        conn.close()


def test_run_sweep_strips_expired_rows(temp_db_path):
    """R-105."""
    conn = db_module.connect(temp_db_path)
    db_module.migrate(conn)
    conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, first_seen, expires_at, expired) "
        "VALUES (?, 'https://x.test/a', 'T', 'S', 'tech', 1, 'D', 1, 1, 0)",
        (b"\x09" * 32,),
    )
    conn.commit()
    conn.close()

    exit_code = run_sweep.main(["--db", str(temp_db_path)])
    assert exit_code == 0

    conn = db_module.connect(temp_db_path)
    try:
        row = conn.execute("SELECT expired, title FROM seen WHERE url_hash = ?", (b"\x09" * 32,)).fetchone()
        assert row["expired"] == 1
        assert row["title"] is None
    finally:
        conn.close()


def test_run_backup_creates_a_dated_backup_file(temp_db_path, tmp_path):
    """R-105. ARCHITECTURE.md §10: dated filename, `.backup` not `cp`."""
    conn = db_module.connect(temp_db_path)
    db_module.migrate(conn)
    conn.close()

    dest_dir = tmp_path / "backups"
    exit_code = run_backup.main(["--db", str(temp_db_path), "--dest-dir", str(dest_dir)])
    assert exit_code == 0

    backups = list(dest_dir.glob("*.db"))
    assert len(backups) == 1, f"expected exactly one dated backup file, got {backups}"
