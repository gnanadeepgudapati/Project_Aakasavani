"""Step 10 acceptance tests. REQUIREMENTS.md R-062..R-064."""

from app.topics import add_topic, list_topics, match_topic, set_topic_enabled, update_topic_query


def _seed(conn, *, n, title, description="d", published_at=1000):
    h = bytes([n]) + b"\x00" * 31
    conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, first_seen, expires_at) "
        "VALUES (?, ?, ?, 'src', 'tech', ?, ?, 1, 999999999999)",
        (h, f"https://x.test/{n}", title, published_at, description),
    )
    conn.commit()
    return h


def test_topic_query_matches(db_conn):
    """R-062."""
    _seed(db_conn, n=1, title="OpenAI releases new model", description="AI news")
    _seed(db_conn, n=2, title="Stock market rallies", description="finance news")

    add_topic(db_conn, "AI", '"OpenAI" OR "machine learning"')

    results = match_topic(db_conn, "AI")
    titles = [r["title"] for r in results]
    assert "OpenAI releases new model" in titles
    assert "Stock market rallies" not in titles


def test_new_topic_is_retroactive(db_conn):
    """R-063. EDITION-AND-UI.md §2.2: 'Add a new topic -> Retroactive
    instantly - matches the whole history.'"""
    _seed(db_conn, n=1, title="Old article about semiconductors", published_at=100)

    # The article existed BEFORE the topic did.
    add_topic(db_conn, "Semiconductors", "semiconductors")

    results = match_topic(db_conn, "Semiconductors")
    assert len(results) == 1
    assert results[0]["title"] == "Old article about semiconductors"


def test_topic_editable(db_conn):
    """R-064."""
    _seed(db_conn, n=1, title="Election results announced")
    _seed(db_conn, n=2, title="Trade tariffs increased")

    add_topic(db_conn, "Geopolitics", "election")
    assert len(match_topic(db_conn, "Geopolitics")) == 1

    # Edit the query string - no retraining, no reprocessing of articles.
    # NB: FTS5's default unicode61 tokenizer does not stem - "tariff" would
    # NOT match "tariffs" (verified directly). Use the real word form.
    update_topic_query(db_conn, "Geopolitics", "election OR tariffs")
    results = match_topic(db_conn, "Geopolitics")
    assert len(results) == 2

    # Disable it - list_topics reflects the change; matching an disabled
    # topic is still possible directly (disabling only affects UI display,
    # per EDITION-AND-UI §2.2's "delete a topic" being the removal path -
    # enabled is a display toggle, not a hard gate here).
    set_topic_enabled(db_conn, "Geopolitics", False)
    topics = {t["name"]: t["enabled"] for t in list_topics(db_conn)}
    assert topics["Geopolitics"] == 0
