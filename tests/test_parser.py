"""Step 06 acceptance tests. REQUIREMENTS.md R-042..R-049."""

from pathlib import Path

from app.ingest.canonical import canonicalize, url_hash
from app.ingest.dedupe import insert_if_new
from app.ingest.parser import parse_feed, resolve_description

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_content_encoded():
    """R-042."""
    raw = (FIXTURES / "feeds" / "with_content_encoded.xml").read_bytes()
    records = parse_feed(raw)
    assert records
    assert records[0].content is not None
    assert len(records[0].content) > 0


def test_missing_content_encoded():
    """R-043."""
    raw = (FIXTURES / "feeds" / "without_content_encoded.xml").read_bytes()
    records = parse_feed(raw)
    assert records
    assert records[0].content is None


def test_malformed_xml_survives():
    """R-044."""
    raw = (FIXTURES / "feeds" / "malformed.xml").read_bytes()
    records = parse_feed(raw)  # must not raise
    assert isinstance(records, list)


def test_empty_feed():
    """R-045."""
    raw = (FIXTURES / "feeds" / "empty.xml").read_bytes()
    records = parse_feed(raw)
    assert records == []


def test_canonicalise_strips_tracking():
    """R-046."""
    dirty = "HTTPS://Example.TEST/Article?utm_source=rss&utm_medium=feed&id=1&fbclid=abc123#section2"
    clean = canonicalize(dirty)
    assert "utm_" not in clean
    assert "fbclid" not in clean
    assert "#" not in clean
    # ARCHITECTURE.md §2.2: lowercase HOST only - paths are case-sensitive on
    # real servers, so the path's original casing ("/Article") must survive.
    assert clean.startswith("https://example.test/Article")
    assert "id=1" in clean  # non-tracking params survive


def test_tracking_params_do_not_change_hash():
    """R-047."""
    a = canonicalize("https://example.test/story?utm_source=rss&utm_campaign=x")
    b = canonicalize("https://example.test/story?utm_source=newsletter")
    assert a == b
    assert url_hash(a) == url_hash(b)

    c = canonicalize("https://example.test/story/")  # trailing slash
    assert canonicalize("https://example.test/story") == c


def test_duplicate_is_skipped(db_conn, frozen_clock):
    """R-048."""
    canon = canonicalize("https://example.test/story-one")
    h = url_hash(canon)

    first = insert_if_new(
        db_conn, url_hash=h, canonical_url=canon, title="T", source="example.test",
        section="tech", published_at=1, description="D",
    )
    assert first is True

    second = insert_if_new(
        db_conn, url_hash=h, canonical_url=canon, title="T (updated headline)",
        source="example.test", section="tech", published_at=1, description="D2",
    )
    assert second is False

    count = db_conn.execute("SELECT COUNT(*) FROM seen WHERE url_hash = ?", (h,)).fetchone()[0]
    assert count == 1


def test_description_fallback_order():
    """R-049."""
    class FakeEntry(dict):
        content = None

    # tier 1: RSS description wins outright
    e1 = FakeEntry(description="RSS blurb", title="Headline")
    assert resolve_description(e1) == "RSS blurb"

    # tier 2: og:description, when no RSS description and page_html given
    e2 = FakeEntry(title="Headline")
    html2 = '<html><head><meta property="og:description" content="OG blurb"></head></html>'
    assert resolve_description(e2, page_html=html2) == "OG blurb"

    # tier 3: twitter:description, when og: is absent
    html3 = '<html><head><meta name="twitter:description" content="Twitter blurb"></head></html>'
    assert resolve_description(e2, page_html=html3) == "Twitter blurb"

    # tier 4: first ~200 chars of body, when the feed shipped content:encoded
    class FakeEntryWithContent(dict):
        pass

    e4 = FakeEntryWithContent(title="Headline")
    e4.content = [type("C", (), {"value": "Body text. " * 30})()]
    result4 = resolve_description(e4)
    assert result4 == ("Body text. " * 30)[:200]

    # tier 5: headline alone, nothing else available
    e5 = FakeEntry(title="Just The Headline")
    assert resolve_description(e5) == "Just The Headline"
