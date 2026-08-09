# 25 — Operational entrypoints + `tests/test_live.py`

`plans/00b-real-data-and-ui-plan.md` Track A step 25. `ARCHITECTURE.md` §10
(cron table). `plans/00-implementation-plan.md` §1 named `tests/test_live.py`
as "MANUAL ONLY. Never in the verify chain" and it was never written — this
is the step that finally delivers it.

## Design

### `scripts/run_build.py` / `run_topup.py` / `run_sweep.py` / `run_backup.py`

Thin CLI wrappers, one per cron line in `ARCHITECTURE.md` §10. Each:

- `--db PATH` flag, defaulting to `AAKASAVANI_DB_PATH` env or
  `<repo_root>/aakasavani.db` — matching `app/web/deps.py`'s existing
  default so the web app and the cron jobs agree on which file is "the"
  database without either importing the other
- connects, runs `app.db.migrate()` (idempotent — safe to call every run)
- `run_build.py`/`run_topup.py` call `sync_feeds_to_db()` **before**
  polling, per the task brief — otherwise a freshly-provisioned DB (or one
  where `feeds.yaml` gained a row) would silently poll a stale or empty
  registry
- honest stdout progress (feed counts, failures, article counts,
  read_minutes) — never silent, per `CLAUDE.md`'s working style
- exit 0 on success; exit 1 with the exception on stderr on an unhandled
  failure. A **per-feed** failure is never fatal (step 23) — only something
  outside that (a DB open failure, a schema problem) should ever produce a
  non-zero exit here
- `run_backup.py` follows `ARCHITECTURE.md` §10's naming:
  `<dest-dir>/<edition_date>.db`, default dest dir `<repo_root>/backups/`

### `tests/test_live.py`

The one deliberate exception to `tests/conftest.py`'s autouse network guard.
**Must not inherit that guard** — so it defines its own throwaway DB and
imports nothing from `conftest.py`. Two mechanisms combine to keep it out of
every automated run:

1. `pyproject.toml`'s `addopts` gains `--ignore=tests/test_live.py`, so a
   bare `pytest` (the verify chain, CI, anything automated) never collects
   it at all — "excluded from testpaths entirely."
2. Manual invocation is `pytest tests/test_live.py --noconftest -v` (or
   simply `python tests/test_live.py`) — `--noconftest` is required because
   pytest would otherwise still load the same-directory `conftest.py` and
   its autouse network guard even for an explicitly-named target.

Test body: `sync_feeds_to_db()` against a real temp DB, disable every feed
except one known-reachable one (from `feeds.yaml`'s own `_audit_status`,
recorded at the step-01 audit — no guessing which feed is up), poll it for
real, assert at least one real `seen` row landed, then run the real
`default_fetcher()` against the most recent one and assert the extraction
shape (either real text ≥ 500 chars, or a recorded failure `reason` — both
are valid honest outcomes per `ARCHITECTURE.md` §2.4, since a single live
run against one real site is not guaranteed to succeed, only to *behave
correctly*).

### Testability without touching the network

`run_build.main()`/`run_topup.main()` accept optional keyword-only
`fetch_fn`/`fetcher` (default `None`, threaded straight through to
`run_build()`/`run_topup()`), the same dependency-injection shape every
other network-touching function in this codebase already uses
(`Fetcher`, `SharedLimiter`, `RobotsCache`, `poll_all_feeds`). Production
invocation (`python scripts/run_build.py`) never passes them, so the real
default wiring (`_default_feed_fetch`, `default_fetcher()`) is what
actually runs in cron — this parameter exists solely so
`tests/test_scripts.py` can inject fixture-only doubles and stay inside
`ARCHITECTURE.md` §12.2's network ban.

## Files

| File | Purpose |
|---|---|
| `scripts/run_build.py` | 04:00 cron entrypoint |
| `scripts/run_topup.py` | :30 top-up cron entrypoint |
| `scripts/run_sweep.py` | 03:00 TTL sweep cron entrypoint |
| `scripts/run_backup.py` | 02:30 backup cron entrypoint |
| `tests/test_scripts.py` | NEW — R-103..R-105, fixture-only doubles injected, zero network |
| `tests/test_live.py` | NEW — manual-only, real-network exception |
| `pyproject.toml` | `addopts` gains `--ignore=tests/test_live.py` (the one permitted edit here) |

## Acceptance criteria

- R-103 `scripts/run_build.py` accepts `--db`, calls `sync_feeds_to_db()` before polling, exits 0 on a successful (possibly partially-failed-feeds) build
- R-104 `scripts/run_topup.py` accepts `--db`, calls `sync_feeds_to_db()` before polling
- R-105 `scripts/run_sweep.py` and `scripts/run_backup.py` accept `--db`, exit 0 on success
- R-106 `tests/test_live.py` exists, is excluded from the default `pytest` run (`pytest --collect-only` never lists it), and — run manually — polls one real feed and extracts one real article, asserting the shape

## Which docs this implements

`ARCHITECTURE.md` §10 (cron table), §12.2 (the one manual network exception), `plans/00-implementation-plan.md` §1.

## What actually happened

`tests/test_scripts.py` (5 tests, R-103..R-105) confirmed red for the right
reason (`ImportError: cannot import name 'run_backup' from 'scripts'`)
before any script existed. One real bug caught by the red-first discipline
itself: `test_run_build_exits_nonzero_on_unhandled_failure` initially
monkeypatched `app.registry.sync_feeds_to_db` (where the function is
*defined*), which had no effect on `scripts/run_build.py`'s already-bound
`from app.registry import sync_feeds_to_db` reference - the test passed for
the wrong reason (it fell through to the real per-feed-failure path, which
IS resilient by design, and returned exit 0). Fixed by patching
`run_build.sync_feeds_to_db` (where it's *looked up*) instead - a genuine
"test was wrong for a subtle reason" catch, not a case of weakening an
assertion.

`--noconftest` confirmed to correctly collect `tests/test_live.py`
standalone (`pytest tests/test_live.py --collect-only --noconftest -q` ->
"1 test collected"). The live network run itself (assertions actually
exercised against the real internet) happens in step 26, where its result
is part of the real-run triage record.

## Requirement IDs closed

R-103, R-104, R-105, R-106 (R-106's live-network assertion is exercised and recorded in step 26).
