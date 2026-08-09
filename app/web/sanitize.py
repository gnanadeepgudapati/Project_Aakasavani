"""D-1 (logs/SESSIONS.md S-006): render-time sanitisation may strip markup
but must never reword or reorder the surviving text - see
tests/test_rules.py::test_render_sanitisation_only_removes_markup.
"""

from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_description(raw: str) -> str:
    without_tags = _TAG_RE.sub("", raw)
    unescaped = html.unescape(without_tags)
    return _WHITESPACE_RE.sub(" ", unescaped).strip()
