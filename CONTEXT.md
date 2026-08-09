# CONTEXT

**Read this first, every session. Rewritten each session, never appended.**

Last updated: 2026-08-09 — supervised build (Prompt 2), step 01 complete

---

## Where the project is

**Planning approved. Step 01 (feed audit) done and green. Steps 02–03 next.**

Repo is on GitHub: `github.com/gnanadeepgudapati/Project_Aakasavani`, `main`,
pushed and tracked. Dev environment is Python 3.14.3 in `.venv/` (see
`logs/SESSIONS.md` S-005 — measured working, not assumed).

## What exists

| Path | State |
|---|---|
| `CLAUDE.md`, `docs/` × 5 | Binding rules + specs. Patched several times this session — see `logs/SESSIONS.md` |
| `REQUIREMENTS.md` | 88 requirements + 19 Ten-Rules, all with `verify:`. **4/88 ticked** (step 01) |
| `plans/00-implementation-plan.md` | Approved |
| `plans/01-feed-audit.md` | Done |
| `BLOCKED.md` | 2 open (B-003 deploy-only, non-blocking; B-004 — 7/35 feeds unreachable, non-blocking). B-001, B-002 resolved/tracked |
| `logs/SESSIONS.md` | S-001…S-006 — see below |
| `.venv/` | Python 3.14.3, `feedparser`/`pyyaml`/`pytest`/`ruff` installed. Gitignored |
| `pyproject.toml` | Deps + pytest config. `app` package registered |
| `app/__init__.py`, `app/config.py`, `app/registry.py` | Minimal — just enough for `import app` and to load/validate `data/feeds.yaml` |
| `data/feeds.yaml` | **The 35 frozen feeds**, audited. 28 reachable, 7 down (`BLOCKED.md` B-004) |
| `scripts/audit_feeds.py` | Run once already. Re-run only if a feed's format changes |
| `tests/test_registry.py` | R-020…R-023, all green |
| `.env.example` | Committed, empty values |

**Not created yet:** `tests/conftest.py`, `tests/test_rules.py`, `fixtures/` —
steps 02 and 03.

## What is decided (`logs/SESSIONS.md` S-001…S-006)

1. Sections = 3: `tech` · `finance` · `world_india`
2. Ingest = RSS only, 35 frozen feeds
3. Front page = 13/section × 3 = 39 (~40)
4. Research panel = Haiku 4.5 only, no Sonnet tier
5. Fixed 3 broken doc cross-refs + the "ship line" (01–09, not "1–5") + Python
   stack recorded as 3.14 dev
6. D-1 Rule 1 verbatim scopes to storage not render; D-2 Rule 6 names
   `/research/*` as the sole network exception; D-3 robots disallow blocks
   Wayback too; D-4 deleted the stale 15-min ingest worker

## What is next

Steps 02 (fixtures + harness) and 03 (`tests/test_rules.py`) — the oracle.
Both must be demonstrated, not just built: for step 03 specifically, each rule
test must be shown catching a real violation (break it, watch red, restore)
before it counts, per Prompt 2. **Stop after step 03. Do not continue to 04**
until the user has watched this and autonomous mode is explicitly authorized.

## Known, non-blocking issue

7 of the 35 frozen feeds are currently unreachable (403/404/malformed) —
`BLOCKED.md` B-004. Not fixed, not substituted, per `SOURCES.md` §1. Revisit
once the front page (step 07) is real and its variety can be judged.

## Where I left off

Step 01 fully green, committed, pushed. About to write `plans/02-fixtures.md`.

## Session-start ritual

Read `CONTEXT.md` → `logs/SESSIONS.md` → `REQUIREMENTS.md`. State where the
project is and what is next. Then continue.

**Never resume from memory of a previous conversation.**
