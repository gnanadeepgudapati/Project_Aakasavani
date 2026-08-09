# 04 — SQLite schema + migrations

`ARCHITECTURE.md` §8 step 04. Schema itself was already fully designed in
`plans/00-implementation-plan.md` §2 during planning (12 documented changes
from the ARCHITECTURE.md §3 draft, including two real bugs: `read_fts`
declared with no sync triggers, and `edition_items.rank` colliding with an
SQLite keyword). This step materializes that design.

## Files

| File | Purpose |
|---|---|
| `app/db.py` | `connect()` (opens connection, sets PRAGMAs), `migrate()` (applies `app/migrations/*.sql` in order, idempotent via `schema_migrations`) |
| `app/migrations/001_initial.sql` | Full schema: `feeds`, `seen`, `read`, `editions`, `edition_items`, `topics`, `ia_queue`, `read_fts`/`seen_fts` + **6 sync triggers** |
| `tests/test_schema.py` | R-028…R-032 |

## What actually happened

All 5 tests passed on the first run — the schema design was already fully
worked out and reviewed during planning (`plans/00-implementation-plan.md`
§2's 12-item change table), so this step was closer to "transcribe the
approved design" than "discover the design via failing tests." The one place
genuine risk existed — the FTS5 sync triggers, since `content='...'`
external-content tables silently yield an empty index without them — was
verified directly: `test_fts_stays_in_sync_on_insert_update_delete` inserts,
updates, and deletes a row and checks the FTS index reflects each change,
including that an UPDATE removes the OLD text from the index (not just adds
the new text) — the exact failure mode the original draft schema had.

Landing this step retroactively turned **R-017** (Rule 9's dwell-columns
check, written at step 03) genuinely green — it only needed the schema to
exist, not the full article view.

## Acceptance criteria — closed

- [x] R-028 `test_schema.py::test_migrations_idempotent`
- [x] R-029 `test_schema.py::test_pragmas_applied`
- [x] R-030 `test_schema.py::test_fts_stays_in_sync_on_insert_update_delete`
- [x] R-031 `test_schema.py::test_edition_items_fk_enforced`
- [x] R-032 `test_schema.py::test_section_check_constraint`
- [x] R-017 (retroactive) `test_rules.py::test_read_schema_has_dwell_columns`

## Which docs this implements

`ARCHITECTURE.md` §3 (as amended by `plans/00-implementation-plan.md` §2),
§8 step 04, §10 (PRAGMA configuration).

## Requirement IDs closed

R-017, R-028, R-029, R-030, R-031, R-032.
