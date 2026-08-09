"""Research panel Timeline tab. ARCHITECTURE.md §2.7, Flow C.

Query order: Wikipedia (curated article, if one exists) -> GDELT DOC 2.0
-> Guardian (only reached if GDELT itself is unavailable - ARCHITECTURE.md
§5: "GDELT down | Chronology degrades to Guardian + Wikipedia only").

Metadata only - title, url, date, source. Article bodies load lazily, only
when the user clicks a specific entry (that's just Flow B / the existing
article view - this module never fetches a body).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TimelineEntry:
    title: str
    url: str
    date: str  # ISO 8601
    source: str


def _default_wikipedia(query: str) -> TimelineEntry | None:
    raise NotImplementedError("real Wikipedia lookup - not wired until deployment")


def _default_gdelt(query: str) -> list[TimelineEntry]:
    raise NotImplementedError("real GDELT DOC 2.0 call - not wired until deployment")


def _default_guardian(query: str) -> list[TimelineEntry]:
    raise NotImplementedError("real Guardian Open Platform call - not wired until deployment")


def get_timeline(
    query: str,
    *,
    wikipedia_fn=None,
    gdelt_fn=None,
    guardian_fn=None,
) -> list[TimelineEntry]:
    wikipedia_fn = wikipedia_fn or _default_wikipedia
    gdelt_fn = gdelt_fn or _default_gdelt
    guardian_fn = guardian_fn or _default_guardian

    entries: list[TimelineEntry] = []

    wiki = wikipedia_fn(query)
    if wiki is not None:
        entries.append(wiki)

    try:
        entries.extend(gdelt_fn(query))
    except Exception:
        # ARCHITECTURE.md §5: GDELT down -> Guardian + Wikipedia only.
        # Wikipedia's result (if any) is already appended above.
        entries.extend(guardian_fn(query))

    entries.sort(key=lambda e: e.date)
    return entries
