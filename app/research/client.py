"""Anthropic Haiku 4.5 wrapper. logs/SESSIONS.md S-004: model pinned, no
Sonnet tier in Phase 1. EDITION-AND-UI.md §3.5's grounding rule: "Always
cite which paragraph an answer came from - a claim the panel can't point at
is a claim you shouldn't trust." Enforced structurally here, not just by
prompting - an out-of-range citation is rejected, not passed through.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

MODEL = "claude-haiku-4-5-20251001"


def _default_ask_call(article_text: str, question: str) -> tuple[str, float]:
    """Real path - never exercised in tests (network-guarded). Returns
    (raw_json_text, usd_cost)."""
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": (
                    "Answer the question using ONLY this article. Respond as "
                    'JSON: {"answer": "...", "cited_paragraph": <0-based index>}.\n\n'
                    f"ARTICLE:\n{article_text}\n\nQUESTION: {question}"
                ),
            }
        ],
    )
    raw_text = resp.content[0].text
    usd_cost = (resp.usage.input_tokens / 1_000_000) * 1.00 + (
        resp.usage.output_tokens / 1_000_000
    ) * 5.00
    return raw_text, usd_cost


def _default_starter_questions_call(article_text: str) -> tuple[str, float]:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": (
                    "Generate 3 specific starter questions a reader might ask "
                    'about this article. Respond as a JSON array of strings.\n\n'
                    f"ARTICLE:\n{article_text}"
                ),
            }
        ],
    )
    raw_text = resp.content[0].text
    usd_cost = (resp.usage.input_tokens / 1_000_000) * 1.00 + (
        resp.usage.output_tokens / 1_000_000
    ) * 5.00
    return raw_text, usd_cost


@dataclass
class AnswerResult:
    text: str
    cited_paragraph: int


def _paragraphs(article_text: str) -> list[str]:
    return [p for p in article_text.split("\n\n") if p.strip()]


def ask_question(article_text: str, question: str, *, call_fn=None) -> tuple[AnswerResult, float]:
    call_fn = call_fn or _default_ask_call
    raw_text, usd_cost = call_fn(article_text, question)
    data = json.loads(raw_text)

    paragraphs = _paragraphs(article_text)
    cited = data["cited_paragraph"]
    if not (0 <= cited < len(paragraphs)):
        raise ValueError(
            f"model cited paragraph {cited}, article has {len(paragraphs)} - "
            f"a claim the panel can't point at is a claim you shouldn't trust "
            f"(EDITION-AND-UI.md §3.5)"
        )

    return AnswerResult(text=data["answer"], cited_paragraph=cited), usd_cost


def generate_starter_questions(article_text: str, *, call_fn=None) -> tuple[list[str], float]:
    call_fn = call_fn or _default_starter_questions_call
    raw_text, usd_cost = call_fn(article_text)
    questions = json.loads(raw_text)
    return questions, usd_cost
