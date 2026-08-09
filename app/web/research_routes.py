"""The research panel's Ask tab (step 15). D-2/S-006, S-008: this is the
ONE place in the reading experience allowed to touch the network - kept in
its own module, separate from app/web/routes.py, so the static Rule-1/Rule-6
checks that walk app.web.routes specifically stay meaningful (a route module
that legitimately imports anthropic would otherwise make those checks
vacuously "pass" by having nothing left to distinguish).
"""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.research.budget import budgeted_call
from app.research.client import MODEL, ask_question, generate_starter_questions
from app.research.explain import explain_selection
from app.research.timeline import get_timeline
from app.web.deps import get_db

router = APIRouter(prefix="/research")

STARTER_QUESTIONS_ESTIMATE_USD = 0.01
ASK_ESTIMATE_USD = 0.01
EXPLAIN_ESTIMATE_USD = 0.005


def _network_guard_triggered(exc: BaseException) -> bool:
    """plans/27-ui-completion.md (G-1). app.research.budget.budgeted_call
    only catches BudgetExceeded around fn() - a real credential failure
    (no ANTHROPIC_API_KEY at all, BLOCKED.md B-002) propagates straight
    through as a raw 500 instead of the "clean, honest state" the panel is
    supposed to show. Wrapping the call below to degrade that gracefully
    must NOT also swallow tests/test_rules.py::test_no_network_on_reading_
    path's proof (R-010, not owned/editable here) that /research/* really
    does reach the network with a syntactically-valid key: that test's own
    docstring establishes the Anthropic SDK wraps a raw connection failure
    in APIConnectionError, so the guard's NetworkAccessError must be found
    by walking __cause__/__context__, exactly as that test does, not by
    isinstance() on the top-level exception. Matched by class NAME (not an
    import of tests.conftest.NetworkAccessError) so this module never
    depends on the test package."""
    cur: BaseException | None = exc
    while cur is not None:
        if type(cur).__name__ == "NetworkAccessError":
            return True
        cur = cur.__cause__ or cur.__context__
    return False


@router.get("/{url_hash_hex}/starter-questions")
def starter_questions(url_hash_hex: str, conn: sqlite3.Connection = Depends(get_db)):
    """EDITION-AND-UI.md §3.3: generated LAZILY on first panel open, cached
    in read.starter_questions so a second open is free."""
    h = bytes.fromhex(url_hash_hex)
    row = conn.execute(
        "SELECT full_text, starter_questions FROM read WHERE url_hash = ?", (h,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404)

    if row["starter_questions"]:
        return {"questions": json.loads(row["starter_questions"]), "cached": True}

    def fn():
        questions, cost = generate_starter_questions(row["full_text"])
        return json.dumps(questions), cost

    try:
        result = budgeted_call(
            conn, STARTER_QUESTIONS_ESTIMATE_USD, fn, model=MODEL, purpose="starter_questions"
        )
    except Exception as exc:
        if _network_guard_triggered(exc):
            raise
        return {"questions": [], "error": "research panel unavailable right now"}
    if result.budget_exceeded:
        return {"questions": [], "error": result.error_message}

    conn.execute(
        "UPDATE read SET starter_questions = ? WHERE url_hash = ?", (result.text, h)
    )
    conn.commit()
    return {"questions": json.loads(result.text), "cached": False}


class AskPayload(BaseModel):
    question: str


@router.post("/{url_hash_hex}/ask")
def ask(url_hash_hex: str, payload: AskPayload, conn: sqlite3.Connection = Depends(get_db)):
    h = bytes.fromhex(url_hash_hex)
    row = conn.execute("SELECT full_text FROM read WHERE url_hash = ?", (h,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404)

    def fn():
        answer, cost = ask_question(row["full_text"], payload.question)
        return json.dumps({"text": answer.text, "cited_paragraph": answer.cited_paragraph}), cost

    try:
        result = budgeted_call(conn, ASK_ESTIMATE_USD, fn, model=MODEL, purpose="question")
    except Exception as exc:
        if _network_guard_triggered(exc):
            raise
        return {"error": "research panel unavailable right now"}
    if result.budget_exceeded:
        return {"error": result.error_message}

    return json.loads(result.text)


@router.get("/{url_hash_hex}/timeline")
def timeline(url_hash_hex: str, query: str, conn: sqlite3.Connection = Depends(get_db)):
    """ARCHITECTURE.md §2.7 Flow C: metadata only, renders in ~1s. Nothing
    here is persisted unless the user opens a specific entry - that becomes
    an ordinary read via the existing /article/{hash} flow, not this route.

    plans/27-ui-completion.md (G-1): app/research/timeline.py's real
    provider functions currently all raise NotImplementedError("not wired
    until deployment") - that module belongs to the other build track and
    is out of scope here. Unmocked, get_timeline() would propagate that
    straight into a raw 500 the first time a human actually opens the
    Timeline tab. Wrapped the same way budgeted_call already degrades the
    Ask/Explain/starter-questions endpoints: a clean {"entries": [],
    "error": ...} instead of a stack trace - the "honest state, not a
    crash" bar the panel is held to for a missing API key applies here too.
    """
    try:
        entries = get_timeline(query)
    except Exception:
        return {"entries": [], "error": "timeline unavailable right now"}

    return {
        "entries": [
            {"title": e.title, "url": e.url, "date": e.date, "source": e.source}
            for e in entries
        ]
    }


class ExplainPayload(BaseModel):
    selection: str


@router.post("/{url_hash_hex}/explain")
def explain(url_hash_hex: str, payload: ExplainPayload, conn: sqlite3.Connection = Depends(get_db)):
    """Uses ONLY payload.selection as context - never looks up or sends the
    article's full_text. See app/research/explain.py's module docstring."""

    def fn():
        return explain_selection(payload.selection)

    try:
        result = budgeted_call(conn, EXPLAIN_ESTIMATE_USD, fn, model=MODEL, purpose="explain")
    except Exception as exc:
        if _network_guard_triggered(exc):
            raise
        return {"error": "research panel unavailable right now"}
    if result.budget_exceeded:
        return {"error": result.error_message}

    return {"explanation": result.text}
