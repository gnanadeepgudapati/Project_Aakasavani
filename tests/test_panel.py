"""Step 15 acceptance tests. REQUIREMENTS.md R-080..R-082."""

import json

import pytest
from fastapi.testclient import TestClient

from app.research.client import ask_question
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
