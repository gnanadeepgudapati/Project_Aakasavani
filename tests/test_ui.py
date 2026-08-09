"""Step 27 acceptance tests (plans/27-ui-completion.md) that don't fit
test_feed_view.py/test_article_view.py/test_panel.py/test_topics.py/
test_search.py cleanly - mostly G-4 (density toggle) and a few G-1 (research
panel) checks that are inherently client-side-only and have no meaningful
HTTP-response-shape assertion, so they're static checks of the shipped
app.css/app.js - the same spirit as tests/test_rules.py's R-001/R-007
static-analysis checks, just for CSS/JS instead of Python import graphs.

REQUIREMENTS.md R-118..R-127.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.edition.swap import atomic_swap
from app.web.deps import get_db
from app.web.main import app

STATIC_DIR = Path(__file__).resolve().parent.parent / "app" / "web" / "static"
CSS = (STATIC_DIR / "app.css").read_text(encoding="utf-8")
JS = (STATIC_DIR / "app.js").read_text(encoding="utf-8")


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


# ── G-4: density toggle - EDITION-AND-UI.md §6.5 ────────────────────────

def test_density_toggle_controls_present(client, db_conn):
    """R-118. Three modes, each a clickable control carrying its mode name,
    present on the rendered page (base.html header - every page gets it)."""
    h1 = _seed_article(db_conn, n=1, section="tech", title="A Tech Headline")
    atomic_swap(db_conn, edition_date="2026-08-09",
                items=[{"url_hash": h1, "section": "tech", "rank_position": 1}])

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-density-option="compact"' in html
    assert 'data-density-option="comfortable"' in html
    assert 'data-density-option="visual"' in html


def test_density_persisted_via_localstorage_key(db_conn):
    """R-118, continued. The toggle must actually persist client-side -
    proven by checking app.js reads/writes a single, specific localStorage
    key for density, consistently."""
    assert "aakasavani:density" in JS
    assert "localStorage.setItem" in JS
    assert "localStorage.getItem" in JS


def test_compact_density_hides_images(client, db_conn):
    """R-119. Compact: 'No images anywhere in the list' (§6.5) - a CSS rule
    scoped to body[data-density="compact"] must hide both hero and
    thumbnail images. Checked in the shipped CSS, not just prose, because
    density is applied client-side with no server round-trip."""
    assert 'data-density="compact"' in CSS
    # Find the compact block and confirm it turns off both image classes.
    idx = CSS.index('data-density="compact"')
    compact_block = CSS[idx:idx + 400]
    assert "hero-image" in compact_block
    assert "thumb-image" in compact_block
    assert "display: none" in compact_block or "display:none" in compact_block


def test_visual_density_gives_thumbnails_hero_treatment(client, db_conn):
    """R-119, continued. Visual: 'Hero treatment throughout' (§6.5) - the
    normally-90px thumbnail must be restyled full-width in this mode,
    reusing the same <img>, not a second image element."""
    assert 'data-density="visual"' in CSS
    idx = CSS.index('data-density="visual"')
    visual_block = CSS[idx:idx + 600]
    assert "thumb-image" in visual_block
    assert "width: 100%" in visual_block or "width:100%" in visual_block


# ── G-1: a few static, client-side-only checks ──────────────────────────

def test_panel_width_persisted_in_localstorage(db_conn):
    """R-123. EDITION-AND-UI.md §3.1: 'Resizable, width remembered.'"""
    assert "aakasavani:panel-width" in JS


def test_explain_js_sends_selection_only(db_conn):
    """R-126. Static twin of test_panel.py::test_explain_uses_selection
    (which proves the SERVER never receives full_text for /explain) - this
    proves the CLIENT never even tries to send it. The fetch body for
    /explain must be built from window.getSelection(), and the payload
    constructed right around that fetch call must not reference full_text -
    scoped to that window rather than the whole file, since an explanatory
    comment elsewhere in app.js is allowed to say the word "full_text" in
    prose without that being the bug this test guards against."""
    assert "getSelection" in JS
    explain_idx = JS.index("/explain")
    window_around_explain = JS[max(0, explain_idx - 600):explain_idx + 400]
    assert "getSelection" in window_around_explain
    assert "full_text" not in window_around_explain


def test_images_collapse_on_error(client, db_conn):
    """R-127. EDITION-AND-UI.md §6.6: 'On image error, collapse the
    element... Never show a broken icon.' _row_thumb.html already had this;
    _row_hero.html did not - both must, now."""
    h1 = _seed_article(db_conn, n=1, section="tech", image_url="https://img.test/1.jpg", title="Hero With Image")
    atomic_swap(db_conn, edition_date="2026-08-09",
                items=[{"url_hash": h1, "section": "tech", "rank_position": 1}])

    resp = client.get("/")
    html = resp.text
    assert "hero-image" in html
    hero_idx = html.index("hero-image")
    tag = html[hero_idx - 20:html.index(">", hero_idx) + 1]
    assert "onerror" in tag, "hero <img> must collapse itself on load failure, just like the thumbnail does"
