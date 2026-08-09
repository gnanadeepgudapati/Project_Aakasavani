# 12 — TTL sweep + backup

`ARCHITECTURE.md` §8 step 12, §10. **Landing this step made every remaining
`test_rules.py` test pass** — R-008 and R-009 (Rule 5, written at step 03)
needed only `app.jobs.sweep`, which didn't exist until now. Full suite: 74/74.

## Files

| File | Purpose |
|---|---|
| `app/jobs/sweep.py` | `sweep_expired_seen()` — strips `title`/`description`/`source`/`full_text`/`fetched_via`, sets `expired=1`, keeps the hash |
| `app/jobs/backup.py` | `backup_db()` — via `Connection.backup()`, not the `sqlite3` CLI |
| `tests/test_sweep.py` | R-069…R-071 |

## Why `.backup()`, not `cp` or the CLI

`ARCHITECTURE.md` §10 says use `.backup`, not `cp`, because it handles an
in-flight write correctly. Went one step further per `plans/00-
implementation-plan.md` risk R-2 (dev is Windows, prod is Ubuntu — the
`sqlite3` CLI may not exist locally): used Python's `sqlite3.Connection.
backup()` API rather than shelling out to the `sqlite3` binary at all, so
backup works identically on whatever platform Python itself runs on.

## What actually happened

All 3 tests passed on the first run. `sweep_expired_seen` reuses the same
`UPDATE` shape already proven correct at step 03/07's rule tests (including
the `full_text`/`fetched_via` columns added by S-007) — no new design risk
here, just wiring an existing, already-validated statement into a callable
job function.

## Acceptance criteria — closed

- [x] R-069…R-071 (`tests/test_sweep.py`, all 3)
- [x] R-008, R-009 (retroactive, `tests/test_rules.py` — **the last two Ten
      Rules tests to close**; all 19 are now green)

## Which docs this implements

`ARCHITECTURE.md` §10 (TTL, sweep SQL as amended by S-007; backup), §12.1
Rule 5.

## Requirement IDs closed

R-008, R-009, R-069, R-070, R-071.
