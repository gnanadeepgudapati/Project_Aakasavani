"""URL canonicalisation + hashing. ARCHITECTURE.md §2.2.

Deliberately does NOT resolve Google News redirect URLs - SOURCES.md's
Google News fallback is not in the frozen 35-feed list (S-002), so that
resolver would be dead code in Phase 1. See plans/00-implementation-plan.md
R-12 and tests/test_registry.py::test_no_google_news_redirect_sources.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_EXACT = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def canonicalize(url: str) -> str:
    """Lowercase host, strip utm_*/fbclid/fragment, drop trailing slash."""
    parts = urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"

    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not (k.lower().startswith(_TRACKING_PREFIXES) or k.lower() in _TRACKING_EXACT)
    ]
    query = urlencode(kept)

    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def url_hash(canonical_url: str) -> bytes:
    return hashlib.sha256(canonical_url.encode("utf-8")).digest()
