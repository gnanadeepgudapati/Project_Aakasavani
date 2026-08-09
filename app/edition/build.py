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

import sqlite3

from app import clock
from app.edition.select import select_edition as _select_edition
from app.edition.swap import atomic_swap
from app.ingest.canonical import canonicalize, url_hash
from app.ingest.dedupe import insert_if_new
from app.ingest.parser import parse_feed
from app.net.fetcher import Fetcher


def poll_all_feeds(conn: sqlite3.Connection, fetch_fn=None) -> int:
    """Fetches every enabled feed row currently in `feeds`, parses, dedupes
    into `seen`. Returns how many NEW rows were inserted. An empty `feeds`
    table (e.g. a fresh test DB nobody seeded) touches the network zero
    times - there is nothing to iterate."""
    if fetch_fn is None:
        from app.net.fetcher import _default_http_get as fetch_fn

    feeds = conn.execute("SELECT * FROM feeds WHERE enabled = 1").fetchall()
    inserted = 0
    for feed in feeds:
        raw = fetch_fn(feed["url"])
        for record in parse_feed(raw):
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
    return inserted


def prefetch_front_page(
    conn: sqlite3.Connection, selection: dict[str, list[sqlite3.Row]], fetcher=None
) -> None:
    """Populates seen.full_text/fetched_via for every selected item -
    EDITION-AND-UI.md §1.3, the reason article opens are instant. Writes
    directly, per-row, so a partial failure mid-edition still leaves whatever
    succeeded usable (this is pre-fetch, not the atomic swap - Rule 7's
    atomicity guarantee is about the EDITION going live, not each fetch)."""
    fetcher = fetcher or Fetcher()
    for rows in selection.values():
        for row in rows:
            result = fetcher.get_full_text(row["canonical_url"])
            if result.text is not None:
                conn.execute(
                    "UPDATE seen SET full_text = ?, fetched_via = ? WHERE url_hash = ?",
                    (result.text, result.fetched_via, row["url_hash"]),
                )
    conn.commit()


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

    prefetch_front_page(conn, selection, fetcher=fetcher)

    items = []
    for section, rows in selection.items():
        for rank, row in enumerate(rows, start=1):
            items.append({"url_hash": row["url_hash"], "section": section, "rank_position": rank})

    edition_date = clock.now_ist().date().isoformat()
    return atomic_swap(conn, edition_date=edition_date, items=items)
