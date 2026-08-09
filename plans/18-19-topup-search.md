# 18-19 — Top-up job + FTS5 search

`ARCHITECTURE.md` §8 steps 18, 19. The last two steps in the currently-planned
scope (`REQUIREMENTS.md` has no entries for 20-22 — `ROADMAP.md`'s "ship and
decide" gate).

## Files

| File | Purpose |
|---|---|
| `app/jobs/topup.py` | `run_topup()` — a thin wrapper around `poll_all_feeds()`, reused rather than duplicated |
| `app/search.py` | `search_read()` — `read`/`read_fts` only |
| `tests/test_topup.py` | R-086, R-087 |
| `tests/test_search.py` | R-088 |

## Design note: top-up's safety is inherited, not reimplemented

`run_topup()` calls the exact same `poll_all_feeds()` step 07 built and
already proved never pre-fetches full text (that only happens in
`prefetch_front_page()`, which top-up never calls) and never touches
`app.edition.select`/`app.edition.swap` at all. R-086/R-087 are really
confirming an invariant that was already true by construction, not adding
new logic.

## What actually happened

All 3 tests (2 topup, 1 search) passed on the first run — both steps reused
already-proven building blocks (`poll_all_feeds` from step 07, the
`read`/`read_fts` schema from step 04) rather than introducing new surface
area.

## Acceptance criteria — closed

- [x] R-086, R-087 (`tests/test_topup.py`)
- [x] R-088 (`tests/test_search.py`)

## Which docs this implements

`EDITION-AND-UI.md` §1.2/§1.5 (top-up cadence, headlines-only); `ARCHITECTURE.md`
§1 (FTS5 search over reads).

## Requirement IDs closed

R-086, R-087, R-088.

---

**This closes all 88 requirements across steps 01-19 — the full currently-
planned scope of `REQUIREMENTS.md`.** Steps 20-22 remain unplanned by design.
One item remains before the Ten Rules oracle is fully honest: the final
violation-demonstration pass promised in `plans/03-rules.md` for the 13 rule
tests that were written correct-by-design but not yet individually shown
catching a real violation.
