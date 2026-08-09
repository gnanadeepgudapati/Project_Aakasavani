# CONTEXT

**Read this first, every session. Rewritten each session, never appended.**

Last updated: 2026-08-08 — planning session (Prompt 1)

---

## Where the project is

**Planning complete. No application code exists. Nothing has been built.**

The repo contains specs, scaffolding, and a git history of exactly one commit.
`app/` does not exist. `tests/` does not exist. `fixtures/` does not exist.

## What exists

| Path | State |
|---|---|
| `CLAUDE.md` | Binding rules. Pre-existing |
| `PROMPT-FOR-CLAUDE-CODE.md` | The three-prompt workflow. Pre-existing |
| `docs/` × 5 | Specs, reference, process, guard rail. Pre-existing |
| `CONTEXT.md` | This file |
| `BLOCKED.md` | **2 open items — both block build step 01** |
| `logs/ERRORS.md` | Empty, indexed |
| `logs/SESSIONS.md` | 4 architectural decisions from the planning session |
| `plans/` | Empty. `plans/01-feed-audit.md` is the next file to write |
| `.workflow/STATE.json` | `current_step: null`, phase `PLANNING` |
| `.workflow/BUDGET.json` | $0.00 spent, caps loaded |
| `.gitignore` | Covers `.workflow/`, `*.db`, fixture cache, `.env` |

**Not created, deliberately:** `REQUIREMENTS.md` (comes after plan approval, per
Prompt 2), `PROGRESS.md` (`git log` is already one).

## What is decided

Four contradictions between the docs were found and closed by the user this
session. All four are recorded in `logs/SESSIONS.md` with the doc patched in the
same commit.

1. **Sections = 3**, per `CLAUDE.md`: `tech` · `finance` · `world_india`
2. **Ingest = RSS only**, the 35 frozen feeds in `SOURCES.md` §1. No arXiv,
   Reddit, GitHub, Finnhub or CoinGecko in Phase 1
3. **Front page = ~40 articles, 13 per section**
4. **Research panel = Haiku 4.5 only** (`claude-haiku-4-5-20251001`). No Sonnet
   "think harder" tier in Phase 1

## What is next

**Blocked on the user.** See `BLOCKED.md`. Two items, both gating step 01:

1. Python version — `CLAUDE.md` pins 3.12; only 3.14.3 and 3.13 are installed
2. Credentials — Anthropic key, archive.org S3, Guardian key

Once unblocked, the sequence is fixed by `ARCHITECTURE.md` §8 and does not vary:

```
01  feed audit          ← NOT code. Fetch 35 feeds once, record has_full_text
02  fixtures + harness  ← the oracle, part 1
03  tests/test_rules.py ← the oracle, part 2
```

Steps 01–03 run **supervised** (Prompt 2). Autonomous mode (Prompt 3) is
forbidden until the user has watched the rule tests catch real violations —
`AUTONOMOUS-LOOP.md` precondition 8.

## Where I left off

End of the planning session. The implementation plan was presented to the user
in-conversation and awaits approval. Nothing was built.

**On approval:** generate `REQUIREMENTS.md` with a `verify:` command on every
line, then write `plans/01-feed-audit.md`, then run step 01.

## Session-start ritual

Read `CONTEXT.md` → `logs/SESSIONS.md` → `REQUIREMENTS.md`. State where the
project is and what is next. Then continue.

**Never resume from memory of a previous conversation.**
