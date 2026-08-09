"""Step 07 acceptance tests. REQUIREMENTS.md R-050..R-053."""

from app.edition.build import prefetch_front_page, run_build
from app.edition.select import select_edition
from app.edition.swap import atomic_swap
from app.net.fetcher import FetchResult


def _seed_seen(conn, *, count, section, base_published_at=1_000_000, weight=3, feed_id=None):
    for i in range(count):
        h = bytes([i % 256]) + section.encode()[:1] + b"\x00" * 30
        conn.execute(
            "INSERT INTO seen (url_hash, canonical_url, title, source, feed_id, "
            "section, published_at, description, first_seen, expires_at) "
            "VALUES (?, ?, ?, 'src', ?, ?, ?, 'd', 1, 999999999999)",
            (h, f"https://x.test/{section}/{i}", f"Title {i}", feed_id, section,
             base_published_at + i),
        )
    conn.commit()


def test_selects_13_per_section(db_conn):
    """R-050."""
    _seed_seen(db_conn, count=20, section="tech")
    _seed_seen(db_conn, count=5, section="finance")  # fewer than 13 available

    selection = select_edition(db_conn)

    assert len(selection["tech"]) == 13
    assert len(selection["finance"]) == 5  # can't select more than exists
    assert selection["world_india"] == []


def test_ranking_recency_then_weight(db_conn):
    """R-051."""
    db_conn.execute(
        "INSERT INTO feeds (url, name, section, source_weight) VALUES "
        "('https://a.test/feed', 'A', 'tech', 1), "
        "('https://b.test/feed', 'B', 'tech', 5)"
    )
    db_conn.commit()
    feed_a = db_conn.execute("SELECT id FROM feeds WHERE name='A'").fetchone()["id"]
    feed_b = db_conn.execute("SELECT id FROM feeds WHERE name='B'").fetchone()["id"]

    # Same published_at (a tie) - weight must break it, higher weight first.
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, feed_id, "
        "section, published_at, description, first_seen, expires_at) VALUES "
        "(?, 'https://a.test/1', 'Low weight, tied time', 'a.test', ?, 'tech', 100, 'd', 1, 999999999999)",
        (b"\x01" * 32, feed_a),
    )
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, feed_id, "
        "section, published_at, description, first_seen, expires_at) VALUES "
        "(?, 'https://b.test/1', 'High weight, tied time', 'b.test', ?, 'tech', 100, 'd', 1, 999999999999)",
        (b"\x02" * 32, feed_b),
    )
    # A clearly more recent, lower-weight item must still rank first (recency wins over weight).
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, feed_id, "
        "section, published_at, description, first_seen, expires_at) VALUES "
        "(?, 'https://a.test/2', 'Low weight, most recent', 'a.test', ?, 'tech', 200, 'd', 1, 999999999999)",
        (b"\x03" * 32, feed_a),
    )
    db_conn.commit()

    rows = select_edition(db_conn)["tech"]
    titles = [r["title"] for r in rows]

    assert titles[0] == "Low weight, most recent", "recency must be the primary key"
    assert titles[1] == "High weight, tied time", "weight breaks a tie in published_at"
    assert titles[2] == "Low weight, tied time"


def test_every_front_page_item_prefetched(db_conn):
    """R-052."""
    _seed_seen(db_conn, count=3, section="tech")
    selection = select_edition(db_conn)

    class FakeFetcher:
        def get_full_text(self, url, feed_content=None):
            return FetchResult(text=f"prefetched body for {url}", fetched_via="live")

    prefetch_front_page(db_conn, selection, fetcher=FakeFetcher())

    rows = db_conn.execute("SELECT url_hash, full_text, fetched_via FROM seen WHERE section='tech'").fetchall()
    assert len(rows) == 3
    for row in rows:
        assert row["full_text"] is not None and row["full_text"].startswith("prefetched body for")
        assert row["fetched_via"] == "live"


def test_swap_only_on_success(db_conn, frozen_clock):
    """R-053."""
    # Seed one existing live edition.
    old_id = atomic_swap(
        db_conn, edition_date="2026-08-08",
        items=[{"url_hash": b"\x99" * 32, "section": "tech", "rank_position": 1}],
    )
    live = db_conn.execute("SELECT id, status FROM editions WHERE id = ?", (old_id,)).fetchone()
    assert live["status"] == "live"

    # A full, real run_build (no feeds registered -> polls nothing, selects
    # nothing, prefetches nothing) must still succeed and swap in a new
    # (empty) edition, superseding the old one.
    new_id = run_build(db_conn)

    new_edition = db_conn.execute("SELECT status FROM editions WHERE id = ?", (new_id,)).fetchone()
    old_edition = db_conn.execute("SELECT status FROM editions WHERE id = ?", (old_id,)).fetchone()
    assert new_edition["status"] == "live"
    assert old_edition["status"] == "superseded"

    live_count = db_conn.execute("SELECT COUNT(*) FROM editions WHERE status='live'").fetchone()[0]
    assert live_count == 1, "exactly one edition must be live at a time"
