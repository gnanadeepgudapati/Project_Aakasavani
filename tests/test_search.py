"""Step 19 acceptance test. REQUIREMENTS.md R-088.

Step 27 additions (plans/27-ui-completion.md, G-3): R-115..R-117 - the
GET /search HTTP route (search.py's search_read() was already tested at the
function level; nothing proved a human could reach it), and search_read()'s
own defensive handling of an empty query.
"""

import pytest
from fastapi.testclient import TestClient

from app.search import search_read
from app.web.deps import get_db
from app.web.main import app


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


def test_empty_query_no_crash(db_conn):
    """R-117, function level. FTS5's MATCH raises OperationalError on an
    empty string - search_read() must fail soft instead."""
    assert search_read(db_conn, "") == []
    assert search_read(db_conn, "   ") == []


@pytest.fixture
def client(db_conn):
    app.dependency_overrides[get_db] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_search_route_renders_matches(client, db_conn):
    """R-115. GET /search?q= is a real route, not just search_read()."""
    db_conn.execute(
        "INSERT INTO read (url_hash, canonical_url, title, source, "
        "published_at, full_text, fetched_via, read_at) VALUES "
        "(?, 'https://x.test/read', 'Giraffe migration patterns explained', "
        "'S', 1, 'giraffe body text', 'feed', 1)",
        (b"\x62" * 32,),
    )
    db_conn.commit()

    resp = client.get("/search?q=Giraffe")
    assert resp.status_code == 200
    assert "Giraffe migration patterns explained" in resp.text


def test_search_route_excludes_unread(client, db_conn):
    """R-116. The HTTP route must carry forward search.py's own `read`-only
    scope (R-088) - an unread `seen`-only match must never surface here."""
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, first_seen, expires_at) VALUES "
        "(?, 'https://x.test/unread', 'Wombat census results released', "
        "'S', 'tech', 1, 'd', 1, 999999999999)",
        (b"\x63" * 32,),
    )
    db_conn.commit()

    resp = client.get("/search?q=Wombat")
    assert resp.status_code == 200
    assert "Wombat census results released" not in resp.text


def test_search_route_empty_query_no_crash(client, db_conn):
    """R-117, route level. Visiting /search with no q, or a blank one, must
    render cleanly - not a 500 from FTS5's MATCH ''."""
    resp = client.get("/search")
    assert resp.status_code == 200

    resp = client.get("/search?q=")
    assert resp.status_code == 200

    resp = client.get("/search?q=   ")
    assert resp.status_code == 200
