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

    result = budgeted_call(
        conn, STARTER_QUESTIONS_ESTIMATE_USD, fn, model=MODEL, purpose="starter_questions"
    )
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

    result = budgeted_call(conn, ASK_ESTIMATE_USD, fn, model=MODEL, purpose="question")
    if result.budget_exceeded:
        return {"error": result.error_message}

    return json.loads(result.text)


@router.get("/{url_hash_hex}/timeline")
def timeline(url_hash_hex: str, query: str, conn: sqlite3.Connection = Depends(get_db)):
    """ARCHITECTURE.md §2.7 Flow C: metadata only, renders in ~1s. Nothing
    here is persisted unless the user opens a specific entry - that becomes
    an ordinary read via the existing /article/{hash} flow, not this route."""
    entries = get_timeline(query)
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

    result = budgeted_call(conn, EXPLAIN_ESTIMATE_USD, fn, model=MODEL, purpose="explain")
    if result.budget_exceeded:
        return {"error": result.error_message}

    return {"explanation": result.text}
