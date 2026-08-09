"""Loads and validates data/feeds.yaml - the frozen feed list.

SOURCES.md §1 is the source of truth for WHICH feeds; this module only reads
what scripts/audit_feeds.py and hand-editing have written to the YAML. It does
not fetch anything itself.
"""

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
