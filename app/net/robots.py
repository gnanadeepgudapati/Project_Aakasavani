"""robots.txt evaluation + per-domain daily cache. ARCHITECTURE.md §6, §10."""

from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

ONE_DAY_SECONDS = 86400


def is_allowed(robots_txt: str, url_path: str, user_agent: str) -> bool:
    """Pure function - no network, no cache. robots_txt is the raw file
    content already fetched by the caller."""
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(robots_txt.splitlines())
    return parser.can_fetch(user_agent, url_path)


@dataclass
class _CacheEntry:
    content: str
    fetched_at: float


class RobotsCache:
    """Fetches robots.txt at most once per domain per day. `fetch_fn` is
    injected so tests never touch the network - it must take a domain and
    return the raw robots.txt text (or None if fetch failed, treated as
    permissive per common practice - a missing robots.txt imposes no
    restriction)."""

    def __init__(self, fetch_fn, clock) -> None:
        self._fetch_fn = fetch_fn
        self._clock = clock
        self._cache: dict[str, _CacheEntry] = {}

    def get(self, domain: str) -> str:
        entry = self._cache.get(domain)
        now = self._clock()
        if entry is not None and (now - entry.fetched_at) < ONE_DAY_SECONDS:
            return entry.content

        content = self._fetch_fn(domain) or ""
        self._cache[domain] = _CacheEntry(content=content, fetched_at=now)
        return content

    def is_fetch_allowed(self, url: str, user_agent: str) -> bool:
        domain = urlparse(url).netloc
        path = urlparse(url).path or "/"
        robots_txt = self.get(domain)
        return is_allowed(robots_txt, path, user_agent)
