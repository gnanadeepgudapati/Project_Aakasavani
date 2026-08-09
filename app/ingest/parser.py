"""Feed parsing + the description fallback chain. ARCHITECTURE.md §2.1, §2.3.

R-002 (Rule 1, D-1): FeedRecord.description is whatever resolve_description's
first applicable tier produces, verbatim from feedparser - no rewording. When
the feed HAS a <description>, that tier wins and the value is exactly what
feedparser parsed (entity-decoded, never re-encoded).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import feedparser

# Matches <meta property="og:description" content="..."> in either attribute
# order, single or double quotes - deliberately simple rather than pulling in
# an HTML parser dependency for one fallback tier CLAUDE.md's Stack table
# doesn't otherwise need.
def _meta_content(html: str, key: str, attr: str) -> str | None:
    pattern = (
        rf'<meta[^>]+{attr}=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']*)["\']'
        rf'|<meta[^>]+content=["\']([^"\']*)["\'][^>]+{attr}=["\']{re.escape(key)}["\']'
    )
    match = re.search(pattern, html, re.IGNORECASE)
    if not match:
        return None
    return match.group(1) or match.group(2)


@dataclass
class FeedRecord:
    url: str
    title: str
    source: str  # domain
    published_at: int | None  # unix seconds, UTC
    description: str
    content: str | None  # <content:encoded> value, if the feed ships one
    image_url: str | None


def _published_at(entry) -> int | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return calendar.timegm(parsed)  # struct_time is UTC; timegm avoids local-tz mktime


def _content_encoded(entry) -> str | None:
    content = getattr(entry, "content", None)
    if not content:
        return None
    value = content[0].value
    return value.strip() or None


def _image_url(entry) -> str | None:
    media_content = entry.get("media_content")
    if media_content:
        url = media_content[0].get("url")
        if url:
            return url
    media_thumb = entry.get("media_thumbnail")
    if media_thumb:
        url = media_thumb[0].get("url")
        if url:
            return url
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image/"):
            return link.get("href")
    return None


def extract_og_image(page_html: bytes | str) -> str | None:
    """D-7 (logs/SESSIONS.md, plans/24-fetcher-wiring-metadata.md):
    EDITION-AND-UI.md §6 images. Called during pre-fetch on page bytes
    already in hand (no extra HTTP request) when the feed shipped no
    image_url of its own. Reuses _meta_content - the same tag-matching
    logic already used for the og:description/twitter:description
    fallback tiers, just a different property."""
    html = page_html.decode("utf-8", errors="replace") if isinstance(page_html, bytes) else page_html
    return _meta_content(html, "og:image", "property")


def resolve_description(entry, page_html: bytes | str | None = None) -> str:
    """ARCHITECTURE.md §2.3 fallback chain:
    RSS description/summary -> og:description -> twitter:description ->
    first ~200 chars of body (if the feed shipped one) -> headline alone.

    og:description/twitter:description need the fetched article page, which
    feed parsing alone doesn't have - callers pass page_html when available
    (post-fetch); parse-time callers leave it None and skip straight past
    those two tiers.
    """
    rss_description = entry.get("description") or entry.get("summary")
    if rss_description:
        return rss_description

    if page_html:
        html = page_html.decode("utf-8", errors="replace") if isinstance(page_html, bytes) else page_html
        og = _meta_content(html, "og:description", "property")
        if og:
            return og
        twitter = _meta_content(html, "twitter:description", "name")
        if twitter:
            return twitter

    content = _content_encoded(entry)
    if content:
        return content[:200]

    return entry.get("title", "")


def parse_feed(raw: bytes) -> list[FeedRecord]:
    """Never raises on malformed XML - feedparser sets .bozo and does its
    best; an empty/malformed feed yields an empty list, not an exception."""
    parsed = feedparser.parse(raw)
    records = []
    for entry in parsed.entries:
        url = entry.get("link", "")
        records.append(
            FeedRecord(
                url=url,
                title=entry.get("title", ""),
                source=urlparse(url).netloc,
                published_at=_published_at(entry),
                description=resolve_description(entry),
                content=_content_encoded(entry),
                image_url=_image_url(entry),
            )
        )
    return records
