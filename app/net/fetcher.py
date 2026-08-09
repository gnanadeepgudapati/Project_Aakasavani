"""ARCHITECTURE.md §2.4: the 3-step full-text fallback, feed -> live -> Wayback.

Rule 8 (shared limiter, honest UA, robots.txt respected) and D-3
(logs/SESSIONS.md S-006: robots disallow blocks the Wayback fallback too,
not just the live fetch) are both structural here, not bolted on: there is
exactly one path to the network (_fetch), and robots is checked before
either live-fetch or Wayback is even attempted.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import USER_AGENT
from app.extract.article import extract_full_text, is_extraction_failure
from app.net.limiter import default_limiter
from app.net.robots import RobotsCache

WAYBACK_BACKOFF_SECONDS = 60.0
WAYBACK_AVAILABLE_API = "https://archive.org/wayback/available?url={url}"


class Wayback429(Exception):
    pass


@dataclass
class FetchResult:
    text: str | None
    fetched_via: str | None  # 'feed' | 'live' | 'wayback' | None
    reason: str | None = None  # set when text is None: why
    page_html: bytes | None = None  # D-7: raw bytes of a page actually
    # fetched (live/wayback only) - None for 'feed' (no network call was
    # made, so there is no page) and None on total failure. Lets a caller
    # extract og:image with no extra HTTP request - the bytes are already
    # in hand.


def _default_http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


@dataclass
class FeedFetchResult:
    """Result of one conditional-GET feed poll. status is the HTTP status
    (200 or 304 - anything else is raised as an exception by
    _default_feed_fetch, for poll_all_feeds' per-feed try/except to catch).
    """

    status: int
    body: bytes | None = None
    etag: str | None = None
    last_modified: str | None = None


def _default_feed_fetch(
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
    limiter=None,
) -> FeedFetchResult:
    """The ONE path to the network for feed polling - always rate-limited.
    D-3 (logs/SESSIONS.md, plans/00b-real-data-and-ui-plan.md):
    poll_all_feeds used to import _default_http_get directly and never
    called limiter.acquire() at all - a live Rule 8 violation.

    D-4: sends If-None-Match/If-Modified-Since from the stored values.
    HTTP 304 is returned as a normal FeedFetchResult (status=304, no
    body) - not raised - since it means "no new items", a success, not a
    failure. Any other non-2xx status, or a network-level failure,
    propagates as an exception for the caller to treat as a poll failure.
    """
    limiter = limiter or default_limiter
    domain = urlparse(url).netloc
    limiter.acquire(domain)

    headers = {"User-Agent": USER_AGENT}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return FeedFetchResult(
                status=resp.status,
                body=resp.read(),
                etag=resp.headers.get("ETag"),
                last_modified=resp.headers.get("Last-Modified"),
            )
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return FeedFetchResult(
                status=304,
                etag=e.headers.get("ETag") or etag,
                last_modified=e.headers.get("Last-Modified") or last_modified,
            )
        raise


def _default_wayback_lookup(url: str) -> str | None:
    api_url = WAYBACK_AVAILABLE_API.format(url=url)
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise Wayback429() from e
        return None
    closest = body.get("archived_snapshots", {}).get("closest")
    if closest and closest.get("available"):
        return closest["url"]
    return None


class Fetcher:
    def __init__(
        self,
        *,
        limiter=None,
        robots_cache=None,
        http_get=None,
        wayback_lookup=None,
        clock=time.monotonic,
    ) -> None:
        self.limiter = limiter or default_limiter
        self.robots_cache = robots_cache
        self._raw_http_get = http_get or _default_http_get
        self._raw_wayback_lookup = wayback_lookup or _default_wayback_lookup
        self.clock = clock
        self._wayback_backoff_until = 0.0

    def _fetch(self, url: str) -> bytes:
        """The ONE path to the network for article bodies - always rate-limited."""
        domain = urlparse(url).netloc
        self.limiter.acquire(domain)
        return self._raw_http_get(url)

    def _wayback_lookup(self, url: str) -> str | None:
        self.limiter.acquire("archive.org")
        return self._raw_wayback_lookup(url)

    def get_full_text(self, url: str, feed_content: str | None = None) -> FetchResult:
        # Step 1: feed content:encoded - free, no network at all.
        if feed_content:
            return FetchResult(text=feed_content, fetched_via="feed")

        # robots.txt gates BOTH remaining steps - D-3.
        if self.robots_cache is not None and not self.robots_cache.is_fetch_allowed(
            url, USER_AGENT
        ):
            return FetchResult(text=None, fetched_via=None, reason="robots_disallow")

        # Step 2: live fetch -> Trafilatura.
        try:
            body = self._fetch(url)
            text = extract_full_text(body)
            if not is_extraction_failure(text):
                return FetchResult(text=text, fetched_via="live", page_html=body)
        except Exception:
            pass  # falls through to Wayback

        # Step 3: Wayback CDX, unless the shared 429 backoff is active.
        if self.clock() < self._wayback_backoff_until:
            return FetchResult(text=None, fetched_via=None, reason="wayback_backoff")

        try:
            snapshot_url = self._wayback_lookup(url)
        except Wayback429:
            self._wayback_backoff_until = self.clock() + WAYBACK_BACKOFF_SECONDS
            return FetchResult(text=None, fetched_via=None, reason="wayback_429")

        if snapshot_url:
            try:
                body = self._fetch(snapshot_url)
                text = extract_full_text(body)
                if not is_extraction_failure(text):
                    return FetchResult(text=text, fetched_via="wayback", page_html=body)
            except Exception:
                pass

        return FetchResult(text=None, fetched_via=None, reason="total_failure")


def _default_robots_fetch(domain: str, limiter=None) -> str | None:
    """Fetches https://{domain}/robots.txt, routed through the shared
    limiter - Rule 8 applies to fetching robots.txt itself, not just to
    what it gates. Returns None on any failure - RobotsCache treats that
    as permissive, per common practice (a missing robots.txt imposes no
    restriction)."""
    limiter = limiter or default_limiter
    limiter.acquire(domain)
    url = f"https://{domain}/robots.txt"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def default_fetcher() -> Fetcher:
    """The real Fetcher used in production. D-6 (logs/SESSIONS.md,
    plans/00b-real-data-and-ui-plan.md, plans/24-fetcher-wiring-
    metadata.md): app.edition.build.prefetch_front_page used to construct
    a bare Fetcher(), leaving robots_cache=None - the robots check's logic
    was correct and unit-tested, but production never passed a cache in,
    so the check was silently skipped on every real run.

    RobotsCache's own 1-day TTL (app.net.robots.ONE_DAY_SECONDS) is
    unchanged; only its fetch function is supplied here, real and
    rate-limited."""
    robots_cache = RobotsCache(fetch_fn=_default_robots_fetch, clock=time.time)
    return Fetcher(robots_cache=robots_cache)
