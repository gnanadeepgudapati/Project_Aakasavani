"""Step 08 acceptance tests. REQUIREMENTS.md R-054..R-058.

Step 27 additions (plans/27-ui-completion.md, G-2): R-111, R-112 - topic
chip filtering (`GET /?topic=`) and its composition with the existing
section filter, at the HTTP route level.
"""

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


def _seed_article(conn, *, n, section, image_url=None, title=None):
    h = bytes([n]) + section.encode()[:1] + b"\x00" * 30
    conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, image_url, first_seen, expires_at) "
        "VALUES (?, ?, ?, 'src.test', ?, ?, 'A description here.', ?, 1, 999999999999)",
        (h, f"https://src.test/{section}/{n}", title or f"{section} article {n}",
         section, 1000 + n, image_url),
    )
    conn.commit()
    return h


def _seed_edition(conn, items_by_section: dict[str, list[bytes]]):
    items = []
    for section, hashes in items_by_section.items():
        for rank, h in enumerate(hashes, start=1):
            items.append({"url_hash": h, "section": section, "rank_position": rank})
    return atomic_swap(conn, edition_date="2026-08-09", items=items)


def test_front_page_renders_edition(client, db_conn):
    """R-054."""
    h1 = _seed_article(db_conn, n=1, section="tech", title="A Tech Headline")
    _seed_edition(db_conn, {"tech": [h1]})

    resp = client.get("/")
    assert resp.status_code == 200
    assert "A Tech Headline" in resp.text


def test_section_chip_filters(client, db_conn):
    """R-055."""
    h1 = _seed_article(db_conn, n=1, section="tech", title="Only Tech Story")
    h2 = _seed_article(db_conn, n=2, section="finance", title="Only Finance Story")
    _seed_edition(db_conn, {"tech": [h1], "finance": [h2]})

    resp = client.get("/?section=tech")
    assert resp.status_code == 200
    assert "Only Tech Story" in resp.text
    assert "Only Finance Story" not in resp.text


def test_hero_on_lead_only(client, db_conn):
    """R-056."""
    h1 = _seed_article(db_conn, n=1, section="tech", image_url="https://img.test/1.jpg", title="Lead Story")
    h2 = _seed_article(db_conn, n=2, section="tech", image_url="https://img.test/2.jpg", title="Second Story")
    h3 = _seed_article(db_conn, n=3, section="tech", image_url="https://img.test/3.jpg", title="Third Story")
    _seed_edition(db_conn, {"tech": [h1, h2, h3]})

    resp = client.get("/")
    html = resp.text

    lead_pos = html.index("Lead Story")
    second_pos = html.index("Second Story")
    third_pos = html.index("Third Story")
    hero_class_pos = html.index('class="row hero')
    thumb_class_positions = [i for i in range(len(html)) if html.startswith('class="row thumb', i)]

    assert hero_class_pos < lead_pos, "hero markup must precede the lead story's own text"
    assert len(thumb_class_positions) == 2, "exactly the two non-lead stories get thumb treatment"
    assert html.count('class="row hero') == 1, "only ONE hero per section"


def test_missing_image_renders_text_only(client, db_conn):
    """R-057."""
    h1 = _seed_article(db_conn, n=1, section="tech", image_url=None, title="No Image Story")
    _seed_edition(db_conn, {"tech": [h1]})

    resp = client.get("/")
    html = resp.text

    assert "No Image Story" in html
    assert "<img" not in html, "no image available must render text-only, never a placeholder"
    assert "text-only" in html


def test_show_everything_lists_remainder(client, db_conn):
    """R-058."""
    h1 = _seed_article(db_conn, n=1, section="tech", title="Front Page Story")
    _seed_edition(db_conn, {"tech": [h1]})

    # 3 more tech articles exist in `seen` but are NOT on the front page.
    for i in range(2, 5):
        _seed_article(db_conn, n=i, section="tech", title=f"Remainder Story {i}")

    resp = client.get("/")
    html = resp.text

    assert "Front Page Story" in html
    for i in range(2, 5):
        assert f"Remainder Story {i}" in html, "remainder articles must be listed, not dropped"
    assert "Show everything (3 more)" in html


def test_topic_chip_filters_front_page(client, db_conn):
    """R-111. Migration 004 seeds an "AI" topic
    ('"artificial intelligence" OR LLM OR OpenAI OR Anthropic OR "machine
    learning"'). Topic filtering is retroactive over ALL of `seen`
    (EDITION-AND-UI.md §2.2), not scoped to today's edition front page - so
    this deliberately does NOT call _seed_edition at all."""
    _seed_article(db_conn, n=1, section="tech", title="OpenAI launches a new coding tool")
    _seed_article(db_conn, n=2, section="tech", title="Local council raises parking fees")

    resp = client.get("/?topic=AI")
    assert resp.status_code == 200
    assert "OpenAI launches a new coding tool" in resp.text
    assert "Local council raises parking fees" not in resp.text


def test_topic_and_section_combine(client, db_conn):
    """R-112. EDITION-AND-UI.md §2.3: "Two chip rows, combinable." A topic
    match in a section the user did NOT select must be excluded."""
    _seed_article(db_conn, n=1, section="tech", title="Anthropic ships a model update")
    _seed_article(db_conn, n=2, section="world_india", title="Anthropic policy debate in parliament")

    resp = client.get("/?topic=AI&section=tech")
    assert resp.status_code == 200
    assert "Anthropic ships a model update" in resp.text
    assert "Anthropic policy debate in parliament" not in resp.text
