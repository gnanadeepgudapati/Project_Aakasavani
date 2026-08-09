"""Step 09 acceptance tests. REQUIREMENTS.md R-059..R-061.

Step 27 addition (plans/27-ui-completion.md, G-1): R-120 - the research
panel's markup exists and is closed by default on every article view.
"""

import pytest
from fastapi.testclient import TestClient

from app.web.deps import get_db
from app.web.main import app

URL_HASH_HEX = "42" * 32
URL_HASH = bytes.fromhex(URL_HASH_HEX)


@pytest.fixture
def client(db_conn):
    app.dependency_overrides[get_db] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_prefetched(conn, *, full_text="Full pre-fetched article body here."):
    conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, full_text, fetched_via, first_seen, expires_at) "
        "VALUES (?, 'https://x.test/a', 'A Title', 'x.test', 'tech', 1000, "
        "'A description', ?, 'live', 1, 999999999999)",
        (URL_HASH, full_text),
    )
    conn.commit()


def test_served_from_prefetch(client, db_conn, monkeypatch):
    """R-059. Opening a front-page article serves pre-fetched text, zero
    fetch calls - patches Fetcher to explode if it's ever constructed,
    proving the pre-fetched path never reaches for it."""
    _seed_prefetched(db_conn, full_text="This exact text was pre-fetched at build time.")

    def _must_not_be_called(*a, **kw):
        raise AssertionError("Fetcher must not be constructed for a pre-fetched article")

    monkeypatch.setattr("app.net.fetcher.Fetcher", _must_not_be_called)

    resp = client.get(f"/article/{URL_HASH_HEX}")
    assert resp.status_code == 200
    assert "This exact text was pre-fetched at build time." in resp.text


def test_dwell_seconds_written(client, db_conn):
    """R-060."""
    _seed_prefetched(db_conn)
    client.get(f"/article/{URL_HASH_HEX}")  # creates the `read` row

    resp = client.post(f"/article/{URL_HASH_HEX}/close", json={"dwell_seconds": 77})
    assert resp.status_code == 200

    row = db_conn.execute(
        "SELECT dwell_seconds FROM read WHERE url_hash = ?", (URL_HASH,)
    ).fetchone()
    assert row["dwell_seconds"] == 77


def test_read_row_created(client, db_conn):
    """R-061."""
    _seed_prefetched(db_conn)

    before = db_conn.execute("SELECT COUNT(*) FROM read").fetchone()[0]
    assert before == 0

    resp = client.get(f"/article/{URL_HASH_HEX}")
    assert resp.status_code == 200

    after = db_conn.execute("SELECT COUNT(*) FROM read WHERE url_hash = ?", (URL_HASH,)).fetchall()
    assert len(after) == 1, "opening an article must create exactly one read row"

    # opening it again must NOT create a second row - already-read path
    client.get(f"/article/{URL_HASH_HEX}")
    count = db_conn.execute("SELECT COUNT(*) FROM read WHERE url_hash = ?", (URL_HASH,)).fetchone()[0]
    assert count == 1


def test_research_panel_present_and_closed(client, db_conn):
    """R-120. EDITION-AND-UI.md Part 3: a right-docked side panel (not a
    modal) with Ask/Timeline/Explain tabs, present on every article view but
    closed until the reader explicitly opens it - `.article-layout` must NOT
    carry `panel-open` on initial render."""
    _seed_prefetched(db_conn)

    resp = client.get(f"/article/{URL_HASH_HEX}")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="research-panel"' in html
    assert 'class="article-layout' in html
    assert "panel-open" not in html.split('<script', 1)[0], (
        "the panel must be closed by default - panel-open is a class app.js "
        "adds only after the reader clicks the open button"
    )
    assert 'data-tab="ask"' in html
    assert 'data-tab="timeline"' in html
    assert 'data-tab="explain"' in html
