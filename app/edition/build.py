"""The 04:00 job. EDITION-AND-UI.md §1.2: poll -> dedupe -> select -> pre-fetch
-> atomic swap. ARCHITECTURE.md §8 step 07.

Rule 4 (test_build_makes_zero_llm_calls, test_no_llm_import_in_build_path):
nothing in this module imports or calls anthropic, and poll_all_feeds only
touches feeds actually present in the `feeds` table - a freshly-migrated,
unseeded test DB has none, so calling run_build() against one makes zero
network calls, not because network is special-cased away, but because
there's nothing registered to poll.
"""

from __future__ import annotations

import math
import sqlite3

from app import clock
from app.edition.select import select_edition as _select_edition
from app.edition.swap import atomic_swap
from app.ingest.canonical import canonicalize, url_hash
from app.ingest.dedupe import insert_if_new
from app.ingest.parser import extract_og_image, parse_feed
from app.net.fetcher import default_fetcher

WORDS_PER_MINUTE = 220  # plans/24-fetcher-wiring-metadata.md, D-8


FAIL_COUNT_DISABLE_THRESHOLD = 10  # ARCHITECTURE.md §5: disable after 10 consecutive failures


def _mark_feed_success(conn: sqlite3.Connection, feed_id: int, *, etag, last_modified, now: int) -> None:
    conn.execute(
        "UPDATE feeds SET etag = ?, last_modified = ?, last_polled = ?, fail_count = 0 WHERE id = ?",
        (etag, last_modified, now, feed_id),
    )
    conn.commit()


def _mark_feed_failure(conn: sqlite3.Connection, feed_id: int, *, current_fail_count: int, now: int) -> None:
    new_count = current_fail_count + 1
    enabled = 0 if new_count >= FAIL_COUNT_DISABLE_THRESHOLD else 1
    conn.execute(
        "UPDATE feeds SET fail_count = ?, last_polled = ?, enabled = ? WHERE id = ?",
        (new_count, now, enabled, feed_id),
    )
    conn.commit()


def poll_all_feeds(conn: sqlite3.Connection, fetch_fn=None) -> int:
    """Fetches every enabled feed row currently in `feeds`, parses, dedupes
    into `seen`. Returns how many NEW rows were inserted across ALL feeds.
    An empty `feeds` table (e.g. a fresh test DB nobody seeded) touches the
    network zero times - there is nothing to iterate.

    D-2/D-5 (logs/SESSIONS.md, plans/23-feed-registry-sync-poll-hardening.md):
    each feed's fetch+parse is isolated in its own try/except - one dead
    feed increments its fail_count and is skipped, but never aborts the
    poll for the other feeds. fail_count resets to 0 on success and the
    feed is disabled (enabled=0) once it reaches 10 consecutive failures.

    D-4: conditional GET - the stored etag/last_modified are sent, and a
    304 (fetch_fn returning status=304) is a successful no-op poll, not a
    failure: zero new rows for that feed, fail_count still resets, but the
    stored etag/last_modified are left untouched since nothing new came
    back to store.

    fetch_fn, when injected (tests), has the signature
    fetch_fn(url, etag, last_modified) -> FeedFetchResult. The default
    (app.net.fetcher._default_feed_fetch) is the one real path to the
    network for feed polling and always goes through the shared limiter -
    D-3.
    """
    if fetch_fn is None:
        from app.net.fetcher import _default_feed_fetch as fetch_fn

    feeds = conn.execute("SELECT * FROM feeds WHERE enabled = 1").fetchall()
    inserted = 0
    now = int(clock.now().timestamp())

    for feed in feeds:
        try:
            result = fetch_fn(feed["url"], feed["etag"], feed["last_modified"])

            if result.status == 304:
                _mark_feed_success(conn, feed["id"], etag=feed["etag"], last_modified=feed["last_modified"], now=now)
                continue

            for record in parse_feed(result.body):
                canon = canonicalize(record.url)
                was_new = insert_if_new(
                    conn,
                    url_hash=url_hash(canon),
                    canonical_url=canon,
                    title=record.title,
                    source=record.source,
                    section=feed["section"],
                    published_at=record.published_at,
                    description=record.description,
                    image_url=record.image_url,
                    feed_id=feed["id"],
                )
                inserted += int(was_new)

            _mark_feed_success(conn, feed["id"], etag=result.etag, last_modified=result.last_modified, now=now)
        except Exception:
            _mark_feed_failure(conn, feed["id"], current_fail_count=feed["fail_count"], now=now)

    return inserted


def prefetch_front_page(
    conn: sqlite3.Connection, selection: dict[str, list[sqlite3.Row]], fetcher=None
) -> int:
    """Populates seen.full_text/fetched_via for every selected item -
    EDITION-AND-UI.md §1.3, the reason article opens are instant. Writes
    directly, per-row, so a partial failure mid-edition still leaves whatever
    succeeded usable (this is pre-fetch, not the atomic swap - Rule 7's
    atomicity guarantee is about the EDITION going live, not each fetch).

    D-6 (plans/24-fetcher-wiring-metadata.md): the default fetcher is
    app.net.fetcher.default_fetcher() - a real Fetcher with a real,
    rate-limited RobotsCache wired in - not a bare Fetcher() with
    robots_cache=None silently skipping the check.

    D-7: when the feed shipped no image_url, extracts og:image from the
    page bytes already fetched for Trafilatura (FetchResult.page_html) -
    no extra HTTP request.

    D-8: returns the total word count of every successfully pre-fetched
    article, for run_build to compute read_minutes from.
    """
    fetcher = fetcher or default_fetcher()
    total_words = 0
    for rows in selection.values():
        for row in rows:
            result = fetcher.get_full_text(row["canonical_url"])
            if result.text is not None:
                total_words += len(result.text.split())
                conn.execute(
                    "UPDATE seen SET full_text = ?, fetched_via = ? WHERE url_hash = ?",
                    (result.text, result.fetched_via, row["url_hash"]),
                )
                if not row["image_url"] and result.page_html:
                    og_image = extract_og_image(result.page_html)
                    if og_image:
                        conn.execute(
                            "UPDATE seen SET image_url = ? WHERE url_hash = ?",
                            (og_image, row["url_hash"]),
                        )
    conn.commit()
    return total_words


def run_build(
    conn: sqlite3.Connection,
    *,
    per_section: int | None = None,
    fetch_fn=None,
    fetcher=None,
) -> int:
    """Returns the new edition's id."""
    poll_all_feeds(conn, fetch_fn=fetch_fn)

    kwargs = {} if per_section is None else {"per_section": per_section}
    selection = _select_edition(conn, **kwargs)

    total_words = prefetch_front_page(conn, selection, fetcher=fetcher)
    read_minutes = math.ceil(total_words / WORDS_PER_MINUTE) if total_words > 0 else None

    items = []
    for section, rows in selection.items():
        for rank, row in enumerate(rows, start=1):
            items.append({"url_hash": row["url_hash"], "section": section, "rank_position": rank})

    edition_date = clock.now_ist().date().isoformat()
    return atomic_swap(conn, edition_date=edition_date, items=items, read_minutes=read_minutes)
