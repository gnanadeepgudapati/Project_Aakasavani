"""Step 13 acceptance tests. REQUIREMENTS.md R-072..R-074."""

import pytest
from fastapi.testclient import TestClient

from app.edition.swap import atomic_swap
from app.web.deps import get_db
from app.web.main import app


@pytest.fixture
def client(db_conn):
    app.dependency_overrides[get_db] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_article(conn, *, n, title):
    h = bytes([n]) + b"\x00" * 31
    conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, first_seen, expires_at) "
        "VALUES (?, ?, ?, 'src', 'tech', ?, 'd', 1, 999999999999)",
        (h, f"https://x.test/{n}", title, 1000 + n),
    )
    conn.commit()
    return h


def test_edition_by_date(client, db_conn):
    """R-072."""
    h1 = _seed_article(db_conn, n=1, title="August Eighth Story")
    atomic_swap(db_conn, edition_date="2026-08-08",
                items=[{"url_hash": h1, "section": "tech", "rank_position": 1}])

    h2 = _seed_article(db_conn, n=2, title="August Ninth Story")
    atomic_swap(db_conn, edition_date="2026-08-09",
                items=[{"url_hash": h2, "section": "tech", "rank_position": 1}])

    resp = client.get("/edition/2026-08-08")
    assert resp.status_code == 200
    assert "August Eighth Story" in resp.text
    assert "August Ninth Story" not in resp.text


def test_unknown_date_404(client, db_conn):
    """R-073."""
    resp = client.get("/edition/2099-01-01")
    assert resp.status_code == 404


def test_root_serves_latest_live(client, db_conn):
    """R-074."""
    h1 = _seed_article(db_conn, n=1, title="Yesterday Lead")
    atomic_swap(db_conn, edition_date="2026-08-08",
                items=[{"url_hash": h1, "section": "tech", "rank_position": 1}])

    h2 = _seed_article(db_conn, n=2, title="Today Lead")
    atomic_swap(db_conn, edition_date="2026-08-09",
                items=[{"url_hash": h2, "section": "tech", "rank_position": 1}])

    live_count = db_conn.execute("SELECT COUNT(*) FROM editions WHERE status='live'").fetchone()[0]
    assert live_count == 1, "the swap must have superseded the first edition"

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # "Today Lead" must be on the FRONT PAGE (before the remainder section).
    # "Yesterday Lead" legitimately still appears in "show everything" - it's
    # unexpired firehose content that just didn't make today's front page,
    # not something R-074 is about. R-074 is only about WHICH edition is
    # live, not about remainder contents (that's R-058's job).
    remainder_start = html.index('class="remainder"')
    assert "Today Lead" in html[:remainder_start]
    assert "Today Lead" not in html[remainder_start:]
