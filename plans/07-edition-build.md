# 07 — Edition build job

`ARCHITECTURE.md` §8 step 07, `EDITION-AND-UI.md` §1.2 (poll → dedupe →
select → pre-fetch → atomic swap).

## A schema gap found and closed mid-step: S-007

While implementing the pre-fetch phase, found that the schema (finished at
step 04) had nowhere to put pre-fetched front-page text. `EDITION-AND-UI.md`
§1.3 says the text is "already in SQLite" before the user opens the article,
but `read` is **permanent** and means "what you actually opened"
(`CLAUDE.md` Rule 5). Writing full text into `read` for all ~39 front-page
articles regardless of whether they're ever opened would be the "permanent
archive of unread articles" `ROADMAP.md` explicitly forbids, and would make
`dwell_seconds`/`read_at` meaningless for un-opened rows.

**Closed as S-007** (`logs/SESSIONS.md`): added `seen.full_text` /
`seen.fetched_via` (migration `002_seen_prefetch.sql`), populated only for
front-page items, `NULL` for the rest (fetched on click, per
`EDITION-AND-UI.md`'s "Show everything... fetched on click, not
pre-fetched"). `seen` already expires in 30 days and Rule 5 already
established it holds strippable text, so this reuses the existing TTL as the
cache's natural bound rather than inventing a new eviction mechanism. Patched
`ARCHITECTURE.md` §3 (schema) and §10 (sweep SQL — two copies existed in the
document; only the first was caught on the initial read and fixed, the
second was found and fixed while doing this patch).

Also strengthened the still-unclosed `test_sweep_strips_text_keeps_hash`
(written at step 03, not yet demonstrable until step 12) to assert
`full_text`/`fetched_via` are stripped too — it hadn't been ticked yet, so
extending it before step 12 builds against it is free.

## Files

| File | Purpose |
|---|---|
| `app/edition/select.py` | `select_edition()` — recency DESC, `source_weight` DESC tiebreak, 13/section |
| `app/edition/swap.py` | `atomic_swap()` — builds into `'building'`, flips to `'live'` in one transaction, rolls back everything on any failure |
| `app/edition/build.py` | `poll_all_feeds()`, `prefetch_front_page()`, `run_build()` — the orchestration |
| `tests/test_edition.py` | R-050…R-053 |

## Design note: why `run_build()` is safe to call against an empty test DB

`test_build_makes_zero_llm_calls` (step 03) calls `run_build(db_conn)` bare,
against a freshly-migrated DB with no seeded data, and expects it to
complete without touching the network. This works because `poll_all_feeds()`
reads the feed list from the `feeds` **table**, not from `data/feeds.yaml`
directly — a fresh test DB has zero rows in `feeds` (loading the registry
into the DB is a separate, not-yet-built concern), so the poll loop iterates
zero times and makes zero requests. Not a special case for tests — just what
naturally happens when nothing is registered to poll.

## What actually happened

All 4 `test_edition.py` tests and the S-007-driven schema change passed on
first real run. One incidental regression, caught immediately: adding
migration 002 broke `test_migrations_idempotent`'s hardcoded
`assert first == [1]` (now `[1, 2]`). Fixed by asserting the migrations
apply in order and are non-empty, rather than hardcoding a count that the
next migration would break again.

**Retroactively closed 3 more rule tests** written at step 03:
`test_build_makes_zero_llm_calls` (R-006), `test_failed_build_keeps_
previous_edition` (R-011), `test_swap_is_atomic` (R-012) — all three needed
only this step's modules, and the monkeypatch targets named in those tests
(`app.edition.build._select_edition`, `app.edition.swap._write_edition_items`)
were designed into `build.py`/`swap.py` from the start to make that possible.

## Acceptance criteria — closed

- [x] R-050…R-053 (`tests/test_edition.py`, all 4)
- [x] R-006, R-011, R-012 (retroactive, `tests/test_rules.py`)

## Which docs this implements

`EDITION-AND-UI.md` §1.2, §1.4 (atomic swap), "Selection — front page
ranking" (as amended by S-003); `ARCHITECTURE.md` §3 (as amended by S-007),
§10 (sweep SQL, as amended by S-007), §12.1 Rules 4 and 7.

## Requirement IDs closed

R-006, R-011, R-012, R-050, R-051, R-052, R-053.
