# 15 — Research panel: Ask tab

`ARCHITECTURE.md` §8 step 15. **First LLM use.** `logs/SESSIONS.md` S-004:
`claude-haiku-4-5-20251001` only, no Sonnet tier.

## Files

| File | Purpose |
|---|---|
| `app/research/client.py` | `ask_question()`, `generate_starter_questions()` — model-pinned, injectable `call_fn` |
| `app/web/research_routes.py` | `GET /research/{hash}/starter-questions`, `POST /research/{hash}/ask` — **its own module**, not `app/web/routes.py` |
| `tests/test_panel.py` | R-080…R-082 |

## Why research routes live in a separate module

`app/web/routes.py` is what `test_no_llm_import_in_render_path` (R-001)
statically walks to prove Anthropic is unreachable from reading. If research
routes lived in that same file, importing `anthropic` there — legitimately,
by design — would make R-001 either fail (wrongly, since the *reading*
handlers still don't touch it) or force weakening the check to "reachable
from *some* handlers is fine," which defeats its purpose. Keeping
`app/web/research_routes.py` separate means R-001 keeps meaning exactly what
it says.

## Grounding enforced structurally, not just by prompt

`EDITION-AND-UI.md` §3.5: "Always cite which paragraph an answer came from —
a claim the panel can't point at is a claim you shouldn't trust." `ask_question()`
validates the model's `cited_paragraph` index against the article's actual
paragraph count and **raises** if it's out of range — `test_out_of_range_
citation_is_rejected` proves a fabricated citation doesn't get silently
passed through.

## Completed R-010's deferred proof

Step 08 could only test half of D-2 (reading routes touch nothing) since
`/research/*` didn't exist. Now it does. Extended `test_no_network_on_
reading_path` to call it unmocked and confirm the *real* SDK path is used:

- No `ANTHROPIC_API_KEY` is configured (`BLOCKED.md` B-002) — without one,
  the SDK fails at local header validation, before ever attempting a
  connection, which would prove nothing about network access.
- A syntactically-valid **fake** key (`monkeypatch.setenv`, test-scoped)
  gets past that local check and reaches the real `connect()` call, which
  the guard intercepts.
- The Anthropic SDK wraps the raw failure in its own `APIConnectionError`
  rather than letting `NetworkAccessError` surface directly — confirmed via
  `__cause__`/`__context__` instead, verified by direct reproduction before
  trusting it in the test.

R-010 is now **fully** demonstrated, not partially.

## Acceptance criteria — closed

- [x] R-080…R-082 (`tests/test_panel.py`, 4 tests total incl. the citation-rejection one)
- [x] R-010 (fully completed, `tests/test_rules.py`)

## Which docs this implements

`EDITION-AND-UI.md` §3.3 (lazy starter questions), §3.5 (grounding rule);
`logs/SESSIONS.md` S-004 (model pin); D-2/S-006, S-008 (network boundary).

## Requirement IDs closed

R-080, R-081, R-082.
