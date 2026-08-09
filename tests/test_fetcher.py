"""Step 05 acceptance tests. REQUIREMENTS.md R-033..R-041."""

import pytest

from app.net.fetcher import Fetcher, Wayback429
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
