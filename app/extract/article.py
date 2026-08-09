"""Trafilatura wrapper. Rule 3: whatever this returns IS what gets stored -
no post-processing step may sit between this and read.full_text anywhere
else in the app.

plans/00-implementation-plan.md R-6: Trafilatura's output depends entirely on
its call signature (default strips images; output format changes the bytes).
Pinned here as the one call this app ever makes, so "the extractor's output"
is a well-defined, single thing - not whatever config happened to be passed
at each call site.
"""

from __future__ import annotations

import trafilatura

from app.config import MIN_EXTRACTION_CHARS

# Pinned. Do not pass different options at different call sites - if the
# extraction needs to change, change it here, once, and re-verify Rule 3.
_EXTRACT_KWARGS = dict(
    include_images=True,   # EDITION-AND-UI.md Part 6 - images extracted with the text
    include_links=False,   # in-body links aren't part of what CLAUDE.md means by "the article"
    output_format="markdown",
    favor_recall=True,     # prefer extracting more over risking an empty result
)


def extract_full_text(html: bytes | str) -> str | None:
    """Returns the extracted text, or None if extraction failed outright."""
    return trafilatura.extract(html, **_EXTRACT_KWARGS)


def is_extraction_failure(text: str | None) -> bool:
    """ARCHITECTURE.md §2.4: <500 chars is a failure, not just an exception -
    catches paywall stubs, consent walls, bot-challenge pages that all
    return 200 OK with a short, useless body."""
    return text is None or len(text) < MIN_EXTRACTION_CHARS
