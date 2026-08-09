"""Step 10 acceptance tests. REQUIREMENTS.md R-062..R-064.

Step 27 additions (plans/27-ui-completion.md, G-2): R-113, R-114 - the
migration seed and the "+ new" HTTP route, not just the underlying
app/topics.py functions R-062..R-064 already covered.
"""

import pytest
from fastapi.testclient import TestClient

from app.topics import add_topic, list_topics, match_topic, set_topic_enabled, update_topic_query
from app.web.deps import get_db
from app.web.main import app


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
    """R-062. Name is "AI Beat", not "AI" - migration 004 (plans/27-ui-
    completion.md, G-2) now seeds a topic literally named "AI" on every
    fresh db_conn, and topics.name is UNIQUE. This test isn't about that
    seeded topic at all, so it uses its own name to avoid the collision
    rather than colliding with seed data incidentally."""
    _seed(db_conn, n=1, title="OpenAI releases new model", description="AI news")
    _seed(db_conn, n=2, title="Stock market rallies", description="finance news")

    add_topic(db_conn, "AI Beat", '"OpenAI" OR "machine learning"')

    results = match_topic(db_conn, "AI Beat")
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
    """R-064. Name is "World Affairs", not "Geopolitics" - migration 004
    (plans/27-ui-completion.md, G-2) now seeds a topic literally named
    "Geopolitics" on every fresh db_conn, and topics.name is UNIQUE. This
    test isn't about that seeded topic at all, so it uses its own name to
    avoid the collision rather than colliding with seed data incidentally."""
    _seed(db_conn, n=1, title="Election results announced")
    _seed(db_conn, n=2, title="Trade tariffs increased")

    add_topic(db_conn, "World Affairs", "election")
    assert len(match_topic(db_conn, "World Affairs")) == 1

    # Edit the query string - no retraining, no reprocessing of articles.
    # NB: FTS5's default unicode61 tokenizer does not stem - "tariff" would
    # NOT match "tariffs" (verified directly). Use the real word form.
    update_topic_query(db_conn, "World Affairs", "election OR tariffs")
    results = match_topic(db_conn, "World Affairs")
    assert len(results) == 2

    # Disable it - list_topics reflects the change; matching an disabled
    # topic is still possible directly (disabling only affects UI display,
    # per EDITION-AND-UI §2.2's "delete a topic" being the removal path -
    # enabled is a display toggle, not a hard gate here).
    set_topic_enabled(db_conn, "World Affairs", False)
    topics = {t["name"]: t["enabled"] for t in list_topics(db_conn)}
    assert topics["World Affairs"] == 0


@pytest.fixture
def client(db_conn):
    app.dependency_overrides[get_db] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_seed_migration_creates_four_topics(db_conn):
    """R-113. EDITION-AND-UI.md §2.2's own 4 example topics, seeded by
    migration 004 so the chip row isn't empty on a fresh install."""
    names = {t["name"] for t in list_topics(db_conn)}
    assert names == {"Energy", "AI", "Geopolitics", "Crypto"}


def test_new_topic_route_creates_and_filters(client, db_conn):
    """R-114. The "+ new" control is a real HTTP route (POST /topics), not
    just the underlying add_topic() function - proven end to end: POST a
    new topic, then GET /?topic=<name> and see it actually filter."""
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, first_seen, expires_at) VALUES "
        "(?, 'https://x.test/robot', 'A story about robotics research', "
        "'S', 'tech', 1, 'd', 1, 999999999999)",
        (b"\x70" * 32,),
    )
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, first_seen, expires_at) VALUES "
        "(?, 'https://x.test/other', 'An unrelated finance story', "
        "'S', 'finance', 1, 'd', 1, 999999999999)",
        (b"\x71" * 32,),
    )
    db_conn.commit()

    resp = client.post("/topics", data={"name": "Robotics", "query": "robotics"})
    assert resp.status_code in (200, 303)

    row = db_conn.execute("SELECT * FROM topics WHERE name = 'Robotics'").fetchone()
    assert row is not None
    assert row["query"] == "robotics"

    resp = client.get("/?topic=Robotics")
    assert resp.status_code == 200
    assert "A story about robotics research" in resp.text
    assert "An unrelated finance story" not in resp.text


def test_new_topic_route_rejects_duplicate_name(client, db_conn):
    """R-114, continued. topics.name is UNIQUE - posting a name that
    already exists must not crash the request with a raw IntegrityError."""
    resp = client.post("/topics", data={"name": "Energy", "query": "oil"})
    assert resp.status_code == 400
