# 16-17 — Research panel: Timeline + Explain tabs

`ARCHITECTURE.md` §8 steps 16, 17. Built together — both are small, both
extend `app/web/research_routes.py`.

## Files

| File | Purpose |
|---|---|
| `app/research/timeline.py` | `get_timeline()` — Wikipedia → GDELT → (GDELT-down only) Guardian, metadata-only |
| `app/research/explain.py` | `explain_selection()` — takes only the highlighted text |
| `app/web/research_routes.py` | `+GET /research/{hash}/timeline`, `+POST /research/{hash}/explain` |
| `tests/test_panel.py` | R-083…R-085 (appended) |

## Design notes

**Timeline degradation matches `ARCHITECTURE.md` §5 exactly:** "GDELT down |
Chronology degrades to Guardian + Wikipedia only" — not "Guardian only."
Wikipedia's result (checked first, independent of GDELT's health) stays in
the list either way; only the GDELT-vs-Guardian branch switches.
`test_gdelt_down_degrades` seeds a GDELT failure and confirms Guardian is
reached, without needing Wikipedia to also fail.

**Explain's context boundary is structural.** `explain_selection()`'s only
parameter is the selection string — there is no code path in
`app/web/research_routes.py`'s `explain()` handler that reads
`row["full_text"]` at all. `test_explain_uses_selection` proves this by
injecting a spy `call_fn` and asserting the received argument doesn't
contain the (much longer) full article text seeded in the same `read` row.

## What actually happened

All 7 tests (3 new step 16/17 tests + the 4 already-existing panel tests)
passed on the first run.

## Acceptance criteria — closed

- [x] R-083, R-084 (`tests/test_panel.py::test_timeline_metadata_only`, `::test_gdelt_down_degrades`)
- [x] R-085 (`tests/test_panel.py::test_explain_uses_selection`)

## Which docs this implements

`ARCHITECTURE.md` §2.7 (live history lookup, query order), §5 (GDELT-down
failure handling); `EDITION-AND-UI.md` §3.2 (panel tabs), §3.5 (token/cost
shape for highlight-to-explain).

## Requirement IDs closed

R-083, R-084, R-085.
