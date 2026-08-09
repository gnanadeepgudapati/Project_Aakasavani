"""Step 19 acceptance test. REQUIREMENTS.md R-088."""

from app.search import search_read


def test_search_scope_is_read(db_conn):
    """R-088. A `seen` row and a `read` row both contain the same
    distinctive term - only the read one may come back."""
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, first_seen, expires_at) VALUES "
        "(?, 'https://x.test/unread', 'Zebranaut unread firehose story', "
        "'S', 'tech', 1, 'd', 1, 999999999999)",
        (b"\x60" * 32,),
    )
    db_conn.execute(
        "INSERT INTO read (url_hash, canonical_url, title, source, "
        "published_at, full_text, fetched_via, read_at) VALUES "
        "(?, 'https://x.test/read', 'Zebranaut actually read story', "
        "'S', 1, 'body mentioning zebranaut again', 'feed', 1)",
        (b"\x61" * 32,),
    )
    db_conn.commit()

    results = search_read(db_conn, "Zebranaut")

    assert len(results) == 1
    assert results[0]["title"] == "Zebranaut actually read story"
