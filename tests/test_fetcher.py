"""Step 05 acceptance tests. REQUIREMENTS.md R-033..R-041.

Step 23 (plans/23-feed-registry-sync-poll-hardening.md) adds the
conditional-GET default feed fetcher - R-094.
Step 24 (plans/24-fetcher-wiring-metadata.md) adds the default_fetcher()
factory (real RobotsCache wiring, D-6) and FetchResult.page_html (D-7) -
R-098, R-099, R-101 (partial).
"""

import pytest

from app.net.fetcher import (
    FeedFetchResult,
    Fetcher,
    Wayback429,
    _default_feed_fetch,
    _default_robots_fetch,
    default_fetcher,
)
from app.net.limiter import SharedLimiter
from app.net.robots import RobotsCache

LONG_TEXT = "A real sentence with real words. " * 30  # > 500 chars
SHORT_TEXT = "Subscribe now."  # < 500 chars, e.g. a paywall stub


def _html_page(paragraph_text: str) -> bytes:
    """Wraps text in enough real HTML structure for Trafilatura to extract
    it - a bare text blob isn't parseable HTML at all."""
    return (
        f"<html><body><article><h1>Test</h1><p>{paragraph_text}</p>"
        f"</article></body></html>"
    ).encode()


class SpyLimiter(SharedLimiter):
    def __init__(self):
        super().__init__(min_interval_seconds=0.0, clock=lambda: 0.0, sleep=lambda s: None)
        self.calls: list[str] = []

    def acquire(self, domain: str) -> float:
        self.calls.append(domain)
        return super().acquire(domain)


def test_one_request_per_second_per_domain():
    """R-033."""
    ticks = [0.0]
    limiter = SharedLimiter(min_interval_seconds=1.0, clock=lambda: ticks[0], sleep=lambda s: None)
    fetcher = Fetcher(limiter=limiter, http_get=lambda url: LONG_TEXT.encode())

    fetcher._fetch("https://example.test/a")
    ticks[0] = 0.3
    waited = limiter.acquire("example.test")
    assert waited >= 0.6


def test_all_fetches_go_through_limiter():
    """R-034."""
    spy = SpyLimiter()
    calls_made = {"live": 0, "wayback_lookup": 0, "wayback_fetch": 0}

    def http_get(url):
        if "archive.org" in url or "web.archive.org" in url:
            calls_made["wayback_fetch"] += 1
            return _html_page(LONG_TEXT)
        calls_made["live"] += 1
        raise ConnectionError("simulate live fetch failure")

    def wayback_lookup(url):
        calls_made["wayback_lookup"] += 1
        return "https://web.archive.org/web/20260101000000/https://example.test/a"

    fetcher = Fetcher(limiter=spy, http_get=http_get, wayback_lookup=wayback_lookup)
    result = fetcher.get_full_text("https://example.test/a")

    assert result.fetched_via == "wayback"
    assert "example.test" in spy.calls, "live-fetch attempt must go through the limiter"
    assert "archive.org" in spy.calls, "wayback lookup must go through the limiter too"


def test_robots_disallow_blocks_fetch():
    """R-035."""
    called = {"http": False}

    def http_get(url):
        called["http"] = True
        return LONG_TEXT.encode()

    robots_cache = RobotsCache(fetch_fn=lambda domain: "User-agent: *\nDisallow: /", clock=lambda: 0.0)
    fetcher = Fetcher(robots_cache=robots_cache, http_get=http_get)

    result = fetcher.get_full_text("https://blocked.test/a")

    assert result.reason == "robots_disallow"
    assert result.text is None
    assert called["http"] is False


def test_robots_cached_per_day():
    """R-036."""
    ticks = [0.0]
    fetch_calls = []

    def fetch_fn(domain):
        fetch_calls.append(domain)
        return "User-agent: *\nAllow: /"

    cache = RobotsCache(fetch_fn=fetch_fn, clock=lambda: ticks[0])

    cache.get("example.test")
    cache.get("example.test")
    assert len(fetch_calls) == 1, "second call within the same day must use the cache"

    ticks[0] = 86400 + 1  # more than a day later
    cache.get("example.test")
    assert len(fetch_calls) == 2, "a call after 1 day must re-fetch"


def test_short_extraction_is_failure():
    """R-037."""
    from app.extract.article import is_extraction_failure

    assert is_extraction_failure(SHORT_TEXT) is True
    assert is_extraction_failure(None) is True
    assert is_extraction_failure(LONG_TEXT) is False


def test_fallback_chain_order():
    """R-038."""
    call_order = []

    def http_get(url):
        if "web.archive.org" in url:
            call_order.append("wayback_fetch")
            return _html_page(LONG_TEXT)
        call_order.append("live")
        raise ConnectionError("live fails")

    def wayback_lookup(url):
        call_order.append("wayback_lookup")
        return "https://web.archive.org/web/20260101000000/https://example.test/a"

    fetcher = Fetcher(http_get=http_get, wayback_lookup=wayback_lookup)
    result = fetcher.get_full_text("https://example.test/a", feed_content=None)

    assert call_order == ["live", "wayback_lookup", "wayback_fetch"]
    assert result.fetched_via == "wayback"

    # feed content:encoded skips both network steps entirely
    call_order.clear()
    result2 = fetcher.get_full_text("https://example.test/b", feed_content=LONG_TEXT)
    assert call_order == []
    assert result2.fetched_via == "feed"


def test_total_failure_returns_headline_only():
    """R-039."""
    fetcher = Fetcher(
        http_get=lambda url: (_ for _ in ()).throw(ConnectionError("down")),
        wayback_lookup=lambda url: None,
    )
    result = fetcher.get_full_text("https://example.test/a")
    assert result.text is None
    assert result.reason == "total_failure"


def test_wayback_429_global_backoff():
    """R-040."""
    ticks = [0.0]
    wayback_lookup_calls = []

    def wayback_lookup(url):
        wayback_lookup_calls.append(url)
        raise Wayback429()

    fetcher = Fetcher(
        http_get=lambda url: (_ for _ in ()).throw(ConnectionError("live fails")),
        wayback_lookup=wayback_lookup,
        clock=lambda: ticks[0],
    )

    r1 = fetcher.get_full_text("https://a.test/1")
    assert r1.reason == "wayback_429"
    assert len(wayback_lookup_calls) == 1

    # a DIFFERENT url, same fetcher (== same shared instance in the real app),
    # shortly after - must skip wayback entirely, proving the backoff is global
    ticks[0] = 1.0
    r2 = fetcher.get_full_text("https://b.test/2")
    assert r2.reason == "wayback_backoff"
    assert len(wayback_lookup_calls) == 1, "backoff must prevent a second real 429"


def test_robots_disallow_blocks_wayback_too():
    """R-041. D-3, logs/SESSIONS.md S-006."""
    wayback_calls = []

    def wayback_lookup(url):
        wayback_calls.append(url)
        return "https://web.archive.org/web/x"

    robots_cache = RobotsCache(fetch_fn=lambda domain: "User-agent: *\nDisallow: /", clock=lambda: 0.0)
    fetcher = Fetcher(
        robots_cache=robots_cache,
        http_get=lambda url: (_ for _ in ()).throw(AssertionError("must not be called")),
        wayback_lookup=wayback_lookup,
    )

    result = fetcher.get_full_text("https://blocked.test/a")

    assert result.reason == "robots_disallow"
    assert wayback_calls == [], "robots disallow must block the Wayback fallback too, not just the live fetch"


# ─────────────────────────────────────────────────────────────────
# Step 23 - conditional-GET default feed fetch. D-3, D-4.
# plans/23-feed-registry-sync-poll-hardening.md
# ─────────────────────────────────────────────────────────────────

def test_default_feed_fetch_sends_conditional_headers_and_handles_304(monkeypatch):
    """R-094. D-4: feeds.etag/last_modified existed as columns and were
    never read into an actual HTTP request. Also proves 304 comes back as
    a normal FeedFetchResult, not a raised exception - and D-3: the fetch
    goes through the shared limiter."""
    import urllib.error
    import urllib.request

    captured_requests = []

    class FakeResponse:
        status = 200
        headers = {"ETag": 'W/"new"', "Last-Modified": "Wed, 03 Jan 2026 00:00:00 GMT"}

        def read(self):
            return b"<rss></rss>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=15):
        captured_requests.append(req)
        if "304please" in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 304, "Not Modified", {"ETag": 'W/"same"'}, None)
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    spy_calls = []
    fake_limiter = SharedLimiter(min_interval_seconds=0.0, clock=lambda: 0.0, sleep=lambda s: None)
    real_acquire = fake_limiter.acquire

    def spy_acquire(domain):
        spy_calls.append(domain)
        return real_acquire(domain)

    fake_limiter.acquire = spy_acquire

    result = _default_feed_fetch(
        "https://example.test/feed",
        etag='W/"old"',
        last_modified="Tue, 02 Jan 2026 00:00:00 GMT",
        limiter=fake_limiter,
    )
    assert result.status == 200
    assert result.body == b"<rss></rss>"
    assert result.etag == 'W/"new"'
    assert result.last_modified == "Wed, 03 Jan 2026 00:00:00 GMT"
    assert "example.test" in spy_calls, "feed fetch must go through the limiter (D-3)"

    sent_headers = {k.lower(): v for k, v in captured_requests[0].headers.items()}
    assert sent_headers.get("if-none-match") == 'W/"old"'
    assert sent_headers.get("if-modified-since") == "Tue, 02 Jan 2026 00:00:00 GMT"

    result_304 = _default_feed_fetch("https://example.test/304please", limiter=fake_limiter)
    assert result_304.status == 304, "304 must be a normal return value, not a raised exception"
    assert isinstance(result_304, FeedFetchResult)


# ─────────────────────────────────────────────────────────────────
# Step 24 - real Fetcher wiring (D-6), page_html for og:image (D-7).
# plans/24-fetcher-wiring-metadata.md
# ─────────────────────────────────────────────────────────────────

def test_default_fetcher_has_a_real_robots_cache():
    """R-098. D-6: prefetch_front_page used to construct a bare Fetcher(),
    leaving robots_cache=None and silently skipping the robots check on
    every real run - the LOGIC was fine, production just never wired it."""
    fetcher = default_fetcher()
    assert fetcher.robots_cache is not None
    from app.net.robots import RobotsCache as RC
    assert isinstance(fetcher.robots_cache, RC)


def test_default_robots_fetch_routes_through_shared_limiter(monkeypatch):
    """R-099. The RobotsCache's own fetch function must not be exempt from
    Rule 8 just because it fetches robots.txt itself."""
    import urllib.request

    class FakeResponse:
        def read(self):
            return b"User-agent: *\nAllow: /"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=15: FakeResponse())

    spy = SpyLimiter()
    result = _default_robots_fetch("example.test", limiter=spy)

    assert "example.test" in spy.calls
    assert result == "User-agent: *\nAllow: /"


def test_fetch_result_carries_page_html_for_live_and_wayback_only():
    """R-101 (partial). D-7: og:image extraction needs the raw page bytes
    already fetched for Trafilatura - no extra HTTP request. page_html
    must be populated for live/wayback (a real page was fetched) and
    absent for the feed tier (content:encoded - no network call at all,
    so there IS no page to extract from)."""
    fetcher = Fetcher(http_get=lambda url: _html_page(LONG_TEXT))

    live_result = fetcher.get_full_text("https://example.test/a")
    assert live_result.fetched_via == "live"
    assert live_result.page_html == _html_page(LONG_TEXT)

    feed_result = fetcher.get_full_text("https://example.test/b", feed_content=LONG_TEXT)
    assert feed_result.fetched_via == "feed"
    assert feed_result.page_html is None
