"""Step 01 acceptance tests. REQUIREMENTS.md R-020..R-023.

No network here - this only reads data/feeds.yaml, which
scripts/audit_feeds.py (the one network-touching step) writes to.
"""

import re

import yaml

from app.config import SECTIONS
from app.registry import load_feeds

SOURCES_MD = "docs/SOURCES.md"


def _frozen_urls_from_sources_md() -> set[str]:
    """Parse the FROZEN feed URLs directly out of SOURCES.md §1.

    Deliberately re-derives the expected list from the doc itself, rather than
    hardcoding a second copy of the 35 URLs in the test - a hardcoded copy
    could drift from SOURCES.md without either ever telling us.
    """
    text = open(SOURCES_MD, encoding="utf-8").read()
    # §1's FROZEN table ends where the fallback subsection begins - those are
    # unfilled URL templates (<query>, <id>), not frozen feeds - and §1 itself
    # ends where §2 (GDELT) begins.
    section = text.split("### Fallback for sources without feeds")[0]
    section = section.split("## 2. GDELT")[0]
    return set(re.findall(r"https?://[^\s|`]+", section))


def test_registry_matches_frozen_list():
    feeds = load_feeds()
    registry_urls = {f["url"] for f in feeds}
    frozen_urls = _frozen_urls_from_sources_md()

    assert registry_urls == frozen_urls, (
        f"missing from registry: {frozen_urls - registry_urls}\n"
        f"extra in registry (not in SOURCES.md §1): {registry_urls - frozen_urls}"
    )
    assert len(feeds) == 35


def test_every_feed_has_section_and_weight():
    feeds = load_feeds()
    for f in feeds:
        assert f["section"] in SECTIONS, f["url"]
        assert isinstance(f["source_weight"], int), f["url"]
        assert 1 <= f["source_weight"] <= 5, f["url"]


def test_has_full_text_recorded_for_every_feed():
    """Every feed was AUDITED. A feed being currently unreachable (403/404/
    malformed) is a legitimate audit outcome, not a missing one - SOURCES.md
    §1 forbids silently substituting a dead feed, so has_full_text staying
    null for those is correct and must be visible in BLOCKED.md instead.
    """
    feeds = load_feeds()
    never_run = [f["url"] for f in feeds if "_audit_status" not in f]
    assert not never_run, (
        f"{len(never_run)} feeds never had the audit run against them - run "
        f"scripts/audit_feeds.py: {never_run}"
    )

    reachable = [f for f in feeds if f["_audit_status"] == "ok"]
    for f in reachable:
        assert isinstance(f["has_full_text"], bool), f["url"]

    unreachable = [f for f in feeds if f["_audit_status"] != "ok"]
    if unreachable:
        blocked_text = open("BLOCKED.md", encoding="utf-8").read()
        not_logged = [f["url"] for f in unreachable if f["url"] not in blocked_text]
        assert not not_logged, (
            f"{len(not_logged)} unreachable feeds not logged in BLOCKED.md, "
            f"per SOURCES.md §1 (\"do not silently swap in another\"): {not_logged}"
        )


def test_no_google_news_redirect_sources():
    feeds = load_feeds()
    for f in feeds:
        assert "news.google.com" not in f["url"], f["url"]
