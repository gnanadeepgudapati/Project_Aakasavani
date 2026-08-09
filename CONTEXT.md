# CONTEXT

**Read this first, every session. Rewritten each session, never appended.**

Last updated: 2026-08-09 — build session complete through step 19

---

## Where the project is

**All 88 requirements across steps 01–19 are closed, 92/92 tests green — and
the product does not work yet.** Read that carefully; it is the single most
important fact in this file.

**2026-08-09: 8 pipeline defects and 4 missing UI features found**, all
verified by reading code, all documented in
`plans/00b-real-data-and-ui-plan.md`. The app **cannot pull real data at
all** — `data/feeds.yaml` is never loaded into the `feeds` table by any
production code path, so a real build polls zero feeds; and one dead feed
would crash the whole build anyway (no error handling), of which 7 are known
dead. Two of the defects (feed polling bypassing the shared limiter;
`robots_cache` never passed to the real `Fetcher`) are **Rule 8 violations on
the real path** that every test missed because every test injected a fake.

Root cause, one sentence: **every component was tested in isolation against
an injected fake, and the assembly that wires them together for a real run
was never built or tested.** `tests/test_live.py` — named in
`plans/00-implementation-plan.md` from the first planning session as exactly
the guard against this — was never written, because no `REQUIREMENTS.md` line
demanded it.

**Next: `plans/00b-real-data-and-ui-plan.md`, steps 23–28.** Track A (steps
23–26) needs no credentials and produces real news on the page.

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

**The app has never been run against real data, and as of 2026-08-09 we know
it currently cannot be.** Every test uses fixtures or injected fakes —
correct per `ARCHITECTURE.md` §12.2 ("tests never touch the network") — but
that is exactly why 8 real defects survived a green suite. See
`plans/00b-real-data-and-ui-plan.md` §1 for the verified list.

**Four Phase-1 UI features named in `ROADMAP.md` have backends but no UI or
routes at all:** the research side panel (4 endpoints exist, nothing on the
page can call them), topic chips, search, and the density toggle. Their
tests passed because they tested the *functions*, never that a human can
reach them.

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
