"""Step 01 acceptance tests. REQUIREMENTS.md R-020..R-023.

Step 23 (plans/23-feed-registry-sync-poll-hardening.md) adds
sync_feeds_to_db - R-089, R-090. No network here - this only reads
data/feeds.yaml, which scripts/audit_feeds.py (the one network-touching
step) writes to.
"""

import re

import yaml

from app.config import SECTIONS
from app.registry import load_feeds, sync_feeds_to_db

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


def test_sync_inserts_every_yaml_feed(db_conn):
    """R-089. D-1 (logs/SESSIONS.md, plans/00b-real-data-and-ui-plan.md):
    nothing wrote feeds.yaml into the `feeds` table at all - poll_all_feeds
    iterated an empty table on every real run, silently."""
    sync_feeds_to_db(db_conn)

    count = db_conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
    assert count == 35

    row = db_conn.execute(
        "SELECT name, section, source_weight, has_full_text, enabled, fail_count "
        "FROM feeds WHERE url = 'https://techcrunch.com/feed/'"
    ).fetchone()
    assert row is not None
    assert row["name"] == "TechCrunch"
    assert row["section"] == "tech"
    assert row["enabled"] == 1
    assert row["fail_count"] == 0


def test_sync_preserves_poll_state_on_existing_rows(db_conn):
    """R-090. A naive DELETE+INSERT would discard every row's etag/
    last_modified/fail_count/enabled on every sync - throwing away 30 days
    of conditional-GET state and un-disabling every feed that had earned
    enabled=0 the hard way. Also proves idempotency: syncing twice with
    unchanged YAML changes nothing on the second pass."""
    sync_feeds_to_db(db_conn)

    url = "https://techcrunch.com/feed/"
    db_conn.execute(
        "UPDATE feeds SET etag = 'W/\"abc123\"', last_modified = 'Mon, 01 Jan 2026 00:00:00 GMT', "
        "fail_count = 7, enabled = 0, last_polled = 1234567890 WHERE url = ?",
        (url,),
    )
    db_conn.commit()

    result = sync_feeds_to_db(db_conn)  # second sync - must not clobber the state just set
    assert result["inserted"] == 0, "no new URLs on a re-sync of the same YAML"

    row = db_conn.execute(
        "SELECT etag, last_modified, fail_count, enabled, last_polled FROM feeds WHERE url = ?",
        (url,),
    ).fetchone()
    assert row["etag"] == 'W/"abc123"'
    assert row["last_modified"] == "Mon, 01 Jan 2026 00:00:00 GMT"
    assert row["fail_count"] == 7
    assert row["enabled"] == 0
    assert row["last_polled"] == 1234567890

    count = db_conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
    assert count == 35, "re-sync must not create duplicate rows"
