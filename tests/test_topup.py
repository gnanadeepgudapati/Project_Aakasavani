"""Step 18 acceptance tests. REQUIREMENTS.md R-086..R-087."""

from app.jobs.topup import run_topup


def _feed_xml(items):
    entries = "".join(
        f"<item><title>{t}</title><link>https://x.test/{i}</link>"
        f"<description>D{i}</description></item>"
        for i, t in enumerate(items)
    )
    return f"<?xml version='1.0'?><rss><channel>{entries}</channel></rss>".encode()


def test_headlines_only(db_conn):
    """R-086."""
    db_conn.execute(
        "INSERT INTO feeds (url, name, section, source_weight, enabled) "
        "VALUES ('https://x.test/feed', 'X', 'tech', 3, 1)"
    )
    db_conn.commit()

    def fetch_fn(url):
        return _feed_xml(["Headline One", "Headline Two"])

    inserted = run_topup(db_conn, fetch_fn=fetch_fn)
    assert inserted == 2

    rows = db_conn.execute("SELECT title, full_text, fetched_via FROM seen").fetchall()
    assert len(rows) == 2
    for row in rows:
        assert row["title"] in ("Headline One", "Headline Two")
        assert row["full_text"] is None, "top-up must never pre-fetch full text"
        assert row["fetched_via"] is None


def test_does_not_rebuild_edition(db_conn):
    """R-087."""
    db_conn.execute(
        "INSERT INTO feeds (url, name, section, source_weight, enabled) "
        "VALUES ('https://x.test/feed', 'X', 'tech', 3, 1)"
    )
    db_conn.commit()

    editions_before = db_conn.execute("SELECT COUNT(*) FROM editions").fetchone()[0]
    edition_items_before = db_conn.execute("SELECT COUNT(*) FROM edition_items").fetchone()[0]

    run_topup(db_conn, fetch_fn=lambda url: _feed_xml(["A New Headline"]))

    editions_after = db_conn.execute("SELECT COUNT(*) FROM editions").fetchone()[0]
    edition_items_after = db_conn.execute("SELECT COUNT(*) FROM edition_items").fetchone()[0]

    assert editions_after == editions_before, "top-up must never create/modify an edition"
    assert edition_items_after == edition_items_before
