"""Step 07 acceptance tests. REQUIREMENTS.md R-050..R-053.

Step 23 (plans/23-feed-registry-sync-poll-hardening.md) adds poll_all_feeds
hardening tests - R-091..R-095.
"""

from app.edition.build import poll_all_feeds, prefetch_front_page, run_build
from app.edition.select import select_edition
from app.edition.swap import atomic_swap
from app.net.fetcher import FeedFetchResult, FetchResult


def _feed_xml(titles):
    entries = "".join(
        f"<item><title>{t}</title><link>https://x.test/{i}</link>"
        f"<description>D{i}</description></item>"
        for i, t in enumerate(titles)
    )
    return f"<?xml version='1.0'?><rss><channel>{entries}</channel></rss>".encode()


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


# ─────────────────────────────────────────────────────────────────
# Step 23 - poll_all_feeds hardening. plans/23-feed-registry-sync-poll-
# hardening.md. Fixes D-2, D-3(partial - see test_rules.py), D-4, D-5.
# ─────────────────────────────────────────────────────────────────

def test_failing_feed_does_not_abort_poll(db_conn):
    """R-091. D-2: poll_all_feeds had NO error handling - one dead feed
    raised and killed the entire build. 7/35 frozen feeds are currently
    dead (BLOCKED.md B-004), so this is the normal case, not the exception."""
    db_conn.execute(
        "INSERT INTO feeds (url, name, section, source_weight, enabled) VALUES "
        "('https://dead.test/feed', 'Dead', 'tech', 3, 1), "
        "('https://alive.test/feed', 'Alive', 'tech', 3, 1)"
    )
    db_conn.commit()

    def fetch_fn(url, etag, last_modified):
        if "dead.test" in url:
            raise ConnectionError("simulated dead feed")
        return FeedFetchResult(status=200, body=_feed_xml(["Live headline"]))

    inserted = poll_all_feeds(db_conn, fetch_fn=fetch_fn)

    assert inserted == 1, "the alive feed's item must still be inserted despite the dead feed"
    titles = [r["title"] for r in db_conn.execute("SELECT title FROM seen").fetchall()]
    assert titles == ["Live headline"]


def test_fail_count_increments_and_resets(db_conn):
    """R-092. ARCHITECTURE.md §5: 'Increment fail_count'; reset on success
    is the corollary needed so a feed that recovers doesn't stay flagged."""
    db_conn.execute(
        "INSERT INTO feeds (url, name, section, source_weight, enabled, fail_count) VALUES "
        "('https://flaky.test/feed', 'Flaky', 'tech', 3, 1, 3)"
    )
    db_conn.commit()

    poll_all_feeds(db_conn, fetch_fn=lambda url, etag, lm: (_ for _ in ()).throw(TimeoutError("simulated")))
    row = db_conn.execute("SELECT fail_count FROM feeds WHERE url='https://flaky.test/feed'").fetchone()
    assert row["fail_count"] == 4

    poll_all_feeds(db_conn, fetch_fn=lambda url, etag, lm: FeedFetchResult(status=200, body=_feed_xml(["Recovered"])))
    row = db_conn.execute("SELECT fail_count FROM feeds WHERE url='https://flaky.test/feed'").fetchone()
    assert row["fail_count"] == 0


def test_feed_disabled_at_ten_consecutive_failures(db_conn):
    """R-093. ARCHITECTURE.md §5: 'disable after 10 consecutive failures'.
    Also proves a disabled feed is skipped on the next poll - dead feeds
    must not be retried forever (D-5)."""
    db_conn.execute(
        "INSERT INTO feeds (url, name, section, source_weight, enabled, fail_count) VALUES "
        "('https://dying.test/feed', 'Dying', 'tech', 3, 1, 9)"
    )
    db_conn.commit()

    poll_all_feeds(db_conn, fetch_fn=lambda url, etag, lm: (_ for _ in ()).throw(ConnectionError("dead")))

    row = db_conn.execute("SELECT fail_count, enabled FROM feeds WHERE url='https://dying.test/feed'").fetchone()
    assert row["fail_count"] == 10
    assert row["enabled"] == 0

    calls = []

    def spy_fetch(url, etag, lm):
        calls.append(url)
        raise AssertionError("a disabled feed must not be polled at all")

    poll_all_feeds(db_conn, fetch_fn=spy_fetch)
    assert calls == [], "poll_all_feeds only selects WHERE enabled = 1"


def test_conditional_get_roundtrip(db_conn):
    """R-095. D-4: feeds.etag/last_modified existed as columns and were
    never read or written. The stored values must reach fetch_fn, and a
    200 response's ETag/Last-Modified headers must be written back."""
    db_conn.execute(
        "INSERT INTO feeds (url, name, section, source_weight, enabled, etag, last_modified) VALUES "
        "('https://cached.test/feed', 'Cached', 'tech', 3, 1, 'W/\"old-etag\"', 'Mon, 01 Jan 2026 00:00:00 GMT')"
    )
    db_conn.commit()

    received = {}

    def fetch_fn(url, etag, last_modified):
        received["etag"], received["last_modified"] = etag, last_modified
        return FeedFetchResult(
            status=200, body=_feed_xml(["New item"]),
            etag='W/"new-etag"', last_modified="Tue, 02 Jan 2026 00:00:00 GMT",
        )

    poll_all_feeds(db_conn, fetch_fn=fetch_fn)

    assert received["etag"] == 'W/"old-etag"'
    assert received["last_modified"] == "Mon, 01 Jan 2026 00:00:00 GMT"

    row = db_conn.execute("SELECT etag, last_modified FROM feeds WHERE url='https://cached.test/feed'").fetchone()
    assert row["etag"] == 'W/"new-etag"'
    assert row["last_modified"] == "Tue, 02 Jan 2026 00:00:00 GMT"


def test_304_is_success_not_failure(db_conn):
    """R-096. ARCHITECTURE.md §2.1: 'Most polls return 304 Not Modified and
    cost nothing.' A 304 must insert zero rows, leave fail_count/etag/
    last_modified untouched, and still advance last_polled."""
    db_conn.execute(
        "INSERT INTO feeds (url, name, section, source_weight, enabled, etag, last_modified, fail_count) VALUES "
        "('https://unchanged.test/feed', 'Unchanged', 'tech', 3, 1, 'W/\"same\"', 'Mon, 01 Jan 2026 00:00:00 GMT', 0)"
    )
    db_conn.commit()

    inserted = poll_all_feeds(db_conn, fetch_fn=lambda url, etag, lm: FeedFetchResult(status=304))

    assert inserted == 0
    row = db_conn.execute(
        "SELECT etag, last_modified, fail_count, last_polled FROM feeds WHERE url='https://unchanged.test/feed'"
    ).fetchone()
    assert row["etag"] == 'W/"same"'
    assert row["last_modified"] == "Mon, 01 Jan 2026 00:00:00 GMT"
    assert row["fail_count"] == 0
    assert row["last_polled"] is not None, "a 304 is still a successful poll attempt"


# ─────────────────────────────────────────────────────────────────
# Step 24 - fetcher wiring + metadata. plans/24-fetcher-wiring-metadata.md.
# Fixes D-6 (see test_rules.py::test_real_build_path_respects_robots_txt),
# D-7, D-8.
# ─────────────────────────────────────────────────────────────────

def test_og_image_populated_only_when_feed_gave_none(db_conn):
    """R-101. D-7: images came only from RSS media:* tags - many feeds
    ship none. og:image is extracted from the page bytes already fetched
    for Trafilatura (no extra request), but only fills the gap - a feed-
    provided image_url must never be overwritten."""
    _seed_seen(db_conn, count=2, section="tech")
    db_conn.execute(
        "UPDATE seen SET image_url = 'https://feed-provided.test/already-has-one.jpg' "
        "WHERE canonical_url = 'https://x.test/tech/0'"
    )
    db_conn.commit()
    selection = select_edition(db_conn)

    page_with_og = (
        b"<html><head><meta property=\"og:image\" "
        b'content="https://extracted.test/hero.jpg"></head>'
        b"<body><article><p>" + (b"Body text. " * 100) + b"</p></article></body></html>"
    )

    class FakeFetcher:
        def get_full_text(self, url, feed_content=None):
            return FetchResult(text="prefetched body", fetched_via="live", page_html=page_with_og)

    prefetch_front_page(db_conn, selection, fetcher=FakeFetcher())

    rows = {
        r["canonical_url"]: r["image_url"]
        for r in db_conn.execute("SELECT canonical_url, image_url FROM seen WHERE section='tech'").fetchall()
    }
    assert rows["https://x.test/tech/0"] == "https://feed-provided.test/already-has-one.jpg", (
        "a feed-provided image must never be overwritten by an extracted one"
    )
    assert rows["https://x.test/tech/1"] == "https://extracted.test/hero.jpg", (
        "a missing feed image must be filled in from the page's og:image"
    )


def test_read_minutes_computed_from_prefetched_word_count(db_conn, frozen_clock):
    """R-102. D-8: atomic_swap accepts read_minutes; run_build never
    computed or passed it, so it was always NULL."""
    _seed_seen(db_conn, count=2, section="tech")

    class FakeFetcher:
        def get_full_text(self, url, feed_content=None):
            return FetchResult(text=" ".join(["word"] * 220), fetched_via="live")  # 220 words = 1 min

    edition_id = run_build(db_conn, fetcher=FakeFetcher())

    edition = db_conn.execute("SELECT read_minutes FROM editions WHERE id = ?", (edition_id,)).fetchone()
    assert edition["read_minutes"] == 2, "2 articles x 220 words = 440 words = ceil(440/220) = 2 minutes"


# ─────────────────────────────────────────────────────────────────
# Step 26 - real-run finding. plans/26-first-real-run-triage.md.
# ─────────────────────────────────────────────────────────────────

def test_200_with_unparseable_xml_is_not_counted_as_a_failure(db_conn):
    """R-109. Found on the first real run against the 35 frozen feeds: The
    Print and Scroll.in (BLOCKED.md B-004) both returned real HTTP 200
    responses with genuinely malformed XML (feedparser bozo=1, 0 entries) -
    not a network/HTTP failure. parse_feed's own contract (R-044) is to
    never raise on malformed XML, so poll_all_feeds' per-feed try/except
    never sees an exception here: this is a *successful* zero-item poll,
    not a failure, and fail_count is correctly left untouched. This
    documents that as INTENTIONAL, current behaviour - a persistently
    malformed-but-2xx feed is never auto-disabled by fail_count alone,
    unlike a 403/404 feed. Flagged in the step 26 report as a real
    ARCHITECTURE.md §5 gap (only 404/timeout are named), not silently
    fixed - deciding whether "0 entries" should count toward fail_count is
    a spec decision outside this task's D-1..D-8 scope."""
    db_conn.execute(
        "INSERT INTO feeds (url, name, section, source_weight, enabled, fail_count) VALUES "
        "('https://malformed-but-200.test/feed', 'MalformedBut200', 'tech', 3, 1, 0)"
    )
    db_conn.commit()

    malformed_xml = b"this is not xml at all, just plain garbage text 12345"  # feedparser: bozo=1, 0 entries

    def fetch_fn(url, etag, last_modified):
        return FeedFetchResult(status=200, body=malformed_xml)

    inserted = poll_all_feeds(db_conn, fetch_fn=fetch_fn)

    assert inserted == 0, "malformed XML parses to zero entries - nothing to insert"
    row = db_conn.execute(
        "SELECT fail_count, enabled, last_polled FROM feeds WHERE url='https://malformed-but-200.test/feed'"
    ).fetchone()
    assert row["fail_count"] == 0, "a 200-with-garbage response is not an exception - not counted as a failure"
    assert row["enabled"] == 1
    assert row["last_polled"] is not None
