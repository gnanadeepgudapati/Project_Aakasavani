"""Step 15 acceptance tests. REQUIREMENTS.md R-080..R-082."""

import json

import pytest
from fastapi.testclient import TestClient

from app.research.client import ask_question
from app.research.timeline import TimelineEntry, get_timeline
from app.web.deps import get_db
from app.web.main import app

URL_HASH_HEX = "77" * 32
URL_HASH = bytes.fromhex(URL_HASH_HEX)
ARTICLE = "First paragraph about the topic.\n\nSecond paragraph with more detail.\n\nThird paragraph, a conclusion."


@pytest.fixture
def client(db_conn):
    app.dependency_overrides[get_db] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_read(conn, *, starter_questions=None):
    conn.execute(
        "INSERT INTO read (url_hash, canonical_url, title, source, published_at, "
        "full_text, fetched_via, read_at, starter_questions) VALUES "
        "(?, 'https://x.test/a', 'T', 'S', 1, ?, 'feed', 1, ?)",
        (URL_HASH, ARTICLE, starter_questions),
    )
    conn.commit()


def test_starter_questions_lazy(client, db_conn, monkeypatch):
    """R-080. Nothing generates starter questions at build time - the build
    job (app.edition.build) never imports or calls anything in
    app.research.*, so the only way this ever runs is a panel open."""
    _seed_read(db_conn)

    call_count = {"n": 0}

    def fake_call(article_text):
        call_count["n"] += 1
        return json.dumps(["Question one?", "Question two?", "Question three?"]), 0.002

    monkeypatch.setattr("app.research.client._default_starter_questions_call", fake_call)

    resp = client.get(f"/research/{URL_HASH_HEX}/starter-questions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cached"] is False
    assert len(data["questions"]) == 3
    assert call_count["n"] == 1

    row = db_conn.execute(
        "SELECT starter_questions FROM read WHERE url_hash = ?", (URL_HASH,)
    ).fetchone()
    assert json.loads(row["starter_questions"]) == data["questions"]


def test_starter_questions_cached(client, db_conn, monkeypatch):
    """R-081."""
    _seed_read(db_conn, starter_questions=json.dumps(["Already cached?"]))

    def must_not_be_called(article_text):
        raise AssertionError("a cached read.starter_questions must not trigger a new call")

    monkeypatch.setattr("app.research.client._default_starter_questions_call", must_not_be_called)

    resp = client.get(f"/research/{URL_HASH_HEX}/starter-questions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cached"] is True
    assert data["questions"] == ["Already cached?"]


def test_answer_cites_paragraph(client, db_conn, monkeypatch):
    """R-082."""
    _seed_read(db_conn)

    def fake_call(article_text, question):
        return json.dumps({"answer": "The answer is in paragraph 2.", "cited_paragraph": 1}), 0.003

    monkeypatch.setattr("app.research.client._default_ask_call", fake_call)

    resp = client.post(f"/research/{URL_HASH_HEX}/ask", json={"question": "What happened?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["cited_paragraph"] == 1
    assert "answer" in data["text"].lower() or len(data["text"]) > 0


def test_out_of_range_citation_is_rejected():
    """R-082, continued: EDITION-AND-UI.md §3.5's grounding rule enforced
    structurally - a citation pointing outside the article must not be
    silently trusted and passed through."""

    def bad_call(article_text, question):
        return json.dumps({"answer": "Fabricated.", "cited_paragraph": 99}), 0.001

    with pytest.raises(ValueError, match="cited paragraph 99"):
        ask_question(ARTICLE, "irrelevant", call_fn=bad_call)


# ── Step 16 - Timeline tab. REQUIREMENTS.md R-083..R-084 ───────────────────

def test_timeline_metadata_only():
    """R-083. Renders from metadata only - no body text field exists on
    TimelineEntry at all; bodies load lazily only when a user clicks a
    specific entry (the existing article view, not this module)."""
    wiki_calls = []
    gdelt_calls = []

    def wikipedia_fn(query):
        wiki_calls.append(query)
        return TimelineEntry(title="Curated Wikipedia Timeline", url="https://wikipedia.test/x",
                              date="2026-01-01", source="wikipedia.org")

    def gdelt_fn(query):
        gdelt_calls.append(query)
        return [
            TimelineEntry(title="Story breaks", url="https://a.test/1", date="2026-01-02", source="a.test"),
            TimelineEntry(title="Follow-up coverage", url="https://b.test/1", date="2026-01-03", source="b.test"),
        ]

    entries = get_timeline("some story", wikipedia_fn=wikipedia_fn, gdelt_fn=gdelt_fn)

    assert len(entries) == 3
    assert [e.title for e in entries] == [
        "Curated Wikipedia Timeline", "Story breaks", "Follow-up coverage",
    ]
    assert not hasattr(entries[0], "body"), "timeline entries must be metadata only"
    assert wiki_calls == ["some story"]
    assert gdelt_calls == ["some story"]


def test_gdelt_down_degrades(db_conn):
    """R-084. ARCHITECTURE.md §5: 'GDELT down | Chronology degrades to
    Guardian + Wikipedia only.'"""
    guardian_calls = []

    def wikipedia_fn(query):
        return None  # no curated article for this one

    def gdelt_fn(query):
        raise ConnectionError("GDELT is down")

    def guardian_fn(query):
        guardian_calls.append(query)
        return [TimelineEntry(title="Guardian archive hit", url="https://guardian.test/1",
                               date="2026-01-01", source="theguardian.com")]

    entries = get_timeline("some story", wikipedia_fn=wikipedia_fn, gdelt_fn=gdelt_fn, guardian_fn=guardian_fn)

    assert len(entries) == 1
    assert entries[0].title == "Guardian archive hit"
    assert guardian_calls == ["some story"]


# ── Step 17 - Explain tab. REQUIREMENTS.md R-085 ────────────────────────────

def test_explain_uses_selection(client, db_conn, monkeypatch):
    """R-085. Explain must use ONLY the user's highlighted text, never the
    full article - proven by a fake call_fn that asserts what it actually
    received."""
    _seed_read(db_conn)  # a `read` row with a much longer full_text exists

    received = {}

    def fake_explain_call(selection):
        received["selection"] = selection
        return "A short explanation.", 0.001

    monkeypatch.setattr("app.research.explain._default_explain_call", fake_explain_call)

    resp = client.post(
        f"/research/{URL_HASH_HEX}/explain", json={"selection": "a highlighted phrase"}
    )
    assert resp.status_code == 200
    assert resp.json()["explanation"] == "A short explanation."

    assert received["selection"] == "a highlighted phrase"
    assert ARTICLE not in received["selection"], "explain must not smuggle in the full article"
