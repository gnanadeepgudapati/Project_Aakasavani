# Project Aakasavani

A personal news reader for one user. Not a product, not multi-tenant. Phase 1
is a finished morning edition plus a research side panel — nothing more.

## The idea

- Wake at 07:00 IST, open one page, read a finished edition that was already
  built and pre-fetched at 04:00 IST. No network wait on click.
- No AI-generated text anywhere in the reading path — headlines and
  descriptions are the outlet's own, verbatim from RSS. No cross-article
  synthesis, no rewriting.
- The only LLM in the system is the research panel, and it runs only when you
  explicitly ask it a question (pull, not push).
- SQLite, single file, single process. No Postgres, no Redis, no message
  broker, no vector DB.

The full rationale for each of these lives in `CLAUDE.md`'s "Ten Rules" — this
file only orients, it doesn't repeat them.

## Status

This project is under active build. **`CONTEXT.md` is the live source of
truth for what exists and what's next** — read it before assuming anything
here is current. `REQUIREMENTS.md`'s ticked boxes (each backed by a passing
`verify:` command) are the source of truth for what's actually been verified,
as opposed to planned.

## Dev setup

Requires Python 3.13+ (developed and verified against 3.14; see
`pyproject.toml` and `CLAUDE.md`'s Stack table — production version is pinned
at deploy time, not yet decided).

```bash
python -m venv .venv

# activate
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"
pytest
```

`pyproject.toml` also defines `extract`, `web`, and `llm` extras — installed
as later build steps need Trafilatura, FastAPI, and the Anthropic SDK
respectively. Not required just to run the current test suite.

## Docs map

| File | What's in it |
|---|---|
| `CLAUDE.md` | Binding project rules: the Ten Rules, the stack, verification philosophy. Start here |
| `docs/ARCHITECTURE.md` | Authoritative spec — system diagram, schema, data flows, failure handling, build order (§8) |
| `docs/EDITION-AND-UI.md` | Authoritative spec — the 04:00 build, atomic swap, categories, images, research panel detail |
| `docs/SOURCES.md` | Reference — feed URLs, GDELT/Guardian/Wayback endpoints, content rights. Feed list is frozen |
| `docs/ROADMAP.md` | Phase 1 / 2 / 3 scope boundaries — what's in, what's deliberately parked |

`CONTEXT.md`, `REQUIREMENTS.md`, `BLOCKED.md`, and `logs/` are working state,
not specs — see `CLAUDE.md` for how each is maintained.
