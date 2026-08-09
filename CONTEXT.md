# CONTEXT

**Read this first, every session. Rewritten each session, never appended.**

Last updated: 2026-08-09 — build session complete through step 19

---

## Where the project is

**All 88 requirements across steps 01–19 are closed. All 19 Ten Rules tests
individually demonstrated catching a real violation. Full suite: 92/92
green.** This is the entire currently-planned scope of `REQUIREMENTS.md`.

Repo: `github.com/gnanadeepgudapati/Project_Aakasavani`, `main`, pushed and
tracked, one commit per step.

## What exists

The whole app, working end to end against fixtures/mocks:

| Area | Modules |
|---|---|
| Registry, schema | `app/registry.py`, `app/db.py`, `app/migrations/*.sql` (3 migrations) |
| Ingest | `app/ingest/{canonical,parser,dedupe}.py` |
| Networking | `app/net/{limiter,robots,fetcher}.py`, `app/extract/article.py` |
| Edition | `app/edition/{select,build,swap}.py` |
| Web (reading) | `app/web/{main,deps,routes,sanitize}.py` + templates + static |
| Web (research) | `app/web/research_routes.py`, `app/research/{client,budget,timeline,explain}.py` |
| Topics, search | `app/topics.py`, `app/search.py` |
| Background jobs | `app/jobs/{sweep,backup,topup}.py`, `app/ia/queue.py` |

`tests/` has one file per step (19 test files, 92 tests), plus
`tests/test_rules.py` (the Ten Rules oracle, 20 tests incl. the
static-analysis self-test) and `tests/conftest.py`/`tests/_static_analysis.py`
(harness).

## What is decided

`logs/SESSIONS.md` S-001 through S-008 — sections/ingest-scope/front-page-size/
model (planning session), then mid-build: S-005 (doc cross-refs, ship line,
Python stack), S-006 (D-1..D-4 rulings), S-007 (schema gap: `seen.full_text`
for pre-fetch, not `read`), S-008 (Rule 6 scopes to front-page articles;
"show everything" fetches on click by design).

## What is NOT done, and why

**Steps 20–22 (deep history, ranking, mobile) are deliberately unplanned.**
`ROADMAP.md`: "Ship steps 01–09 and live with it for two weeks before
building anything below." No `REQUIREMENTS.md` entries exist for them —
adding requirements for an unplanned step would itself be a "wish with no
verify," the exact thing `REQUIREMENTS.md` forbids. This isn't something left
undone; it's the project's own explicit gate, not mine to open.

**The app has never been run against real data.** Every test uses fixtures
or injected fakes — genuinely correct per `ARCHITECTURE.md` §12.2 ("tests
never touch the network"), but it means nobody has watched a real 04:00
build produce a real edition from the real 35 feeds yet. See `BLOCKED.md`
for what's needed to do that (mainly: a Python-version decision for
deployment, and credentials — all optional, none block the code as it
stands).

## Known, non-blocking issues carried from earlier steps

- `BLOCKED.md` B-003 — deploy-time Python version (3.14 dev vs 3.12 prod Ubuntu). Not urgent.
- `BLOCKED.md` B-004 — 7 of 35 frozen feeds were unreachable at the step-01 audit (2026-08-09). Not fixed, not substituted, per `SOURCES.md` §1.

## Where I left off

Everything committed and pushed through the step-99 violation-demonstration
pass. See `BLOCKED.md` for the final report and what's needed to go from
"tested" to "actually running."

## Session-start ritual

Read `CONTEXT.md` → `logs/SESSIONS.md` → `REQUIREMENTS.md`. State where the
project is and what is next. Then continue.

**Never resume from memory of a previous conversation.**
