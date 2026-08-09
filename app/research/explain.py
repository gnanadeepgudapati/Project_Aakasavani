"""Research panel Explain tab (highlight-to-explain). EDITION-AND-UI.md §3.2,
§3.5. Deliberately takes ONLY the user's selected text, never the whole
article - a highlight-to-explain that silently included full-article context
would be answering a different, unasked question, and would cost roughly
5x more per EDITION-AND-UI.md §3.5's own token estimates (~1k in for a
selection vs. ~5k in for a full question).
"""

from __future__ import annotations

MODEL = "claude-haiku-4-5-20251001"


def _default_explain_call(selection: str) -> tuple[str, float]:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=150,
        messages=[
            {"role": "user", "content": f"Explain this simply, in 1-2 sentences:\n\n{selection}"}
        ],
    )
    text = resp.content[0].text
    usd_cost = (resp.usage.input_tokens / 1_000_000) * 1.00 + (
        resp.usage.output_tokens / 1_000_000
    ) * 5.00
    return text, usd_cost


def explain_selection(selection: str, *, call_fn=None) -> tuple[str, float]:
    call_fn = call_fn or _default_explain_call
    return call_fn(selection)
