"""Loads and validates data/feeds.yaml - the frozen feed list.

SOURCES.md §1 is the source of truth for WHICH feeds; this module only reads
what scripts/audit_feeds.py and hand-editing have written to the YAML. It does
not fetch anything itself.

sync_feeds_to_db() (step 23, plans/23-feed-registry-sync-poll-hardening.md,
D-1) is the one place that writes the YAML into the `feeds` table -
poll_all_feeds (app/edition/build.py) only ever reads from that table.
"""

import sqlite3
from pathlib import Path

import yaml

from app.config import FEEDS_YAML_PATH, SECTIONS


class RegistryError(ValueError):
    """A feeds.yaml entry violates the registry's own invariants."""


def load_feeds(path: Path = FEEDS_YAML_PATH) -> list[dict]:
    """Read and validate every entry in feeds.yaml. Raises RegistryError."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    feeds = data.get("feeds") if data else None
    if not feeds:
        raise RegistryError(f"{path} has no 'feeds' list")

    seen_urls = set()
    for entry in feeds:
        url = entry.get("url")
        if not url:
            raise RegistryError(f"entry missing url: {entry!r}")
        if url in seen_urls:
            raise RegistryError(f"duplicate url in registry: {url}")
        seen_urls.add(url)

        if entry.get("section") not in SECTIONS:
            raise RegistryError(
                f"{url}: section {entry.get('section')!r} not in {SECTIONS}"
            )

        weight = entry.get("source_weight")
        if not isinstance(weight, int) or not (1 <= weight <= 5):
            raise RegistryError(f"{url}: source_weight {weight!r} not in 1..5")

    return feeds


def sync_feeds_to_db(conn: sqlite3.Connection, path: Path = FEEDS_YAML_PATH) -> dict:
    """Upserts every data/feeds.yaml entry into the `feeds` table, keyed by
    url. D-1: `poll_all_feeds` reads only from this table, and nothing
    previously wrote it - every real run polled zero feeds, silently.

    Critically preserves etag/last_modified/fail_count/enabled on rows that
    already exist - those are poll STATE, not registry DATA, and a naive
    DELETE+INSERT would erase 30 days of conditional-GET history and
    un-disable every feed that had earned enabled=0 the hard way. Only
    name/section/source_weight/has_full_text (registry data proper) are
    ever overwritten on an existing row.

    Idempotent: a second call with unchanged YAML changes nothing. Rows
    whose url is no longer in the YAML are left alone, not deleted - the
    frozen list only grows or is explicitly retired via a SESSIONS entry,
    never silently vanishes from a poll's perspective.

    Returns {"inserted": N, "updated": M}.
    """
    feeds = load_feeds(path)
    inserted = 0
    updated = 0

    for f in feeds:
        has_full_text = 1 if f.get("has_full_text") else 0
        existing = conn.execute(
            "SELECT id FROM feeds WHERE url = ?", (f["url"],)
        ).fetchone()

        if existing is None:
            conn.execute(
                "INSERT INTO feeds (url, name, section, source_weight, has_full_text) "
                "VALUES (?, ?, ?, ?, ?)",
                (f["url"], f["name"], f["section"], f["source_weight"], has_full_text),
            )
            inserted += 1
        else:
            conn.execute(
                "UPDATE feeds SET name = ?, section = ?, source_weight = ?, has_full_text = ? "
                "WHERE url = ?",
                (f["name"], f["section"], f["source_weight"], has_full_text, f["url"]),
            )
            updated += 1

    conn.commit()
    return {"inserted": inserted, "updated": updated}
