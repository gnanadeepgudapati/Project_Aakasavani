# 14 — Budget wrapper

`ARCHITECTURE.md` §8 step 14, §6 ("checked before calling and raises
BudgetExceeded... A ledger appended to after the fact does not cap
anything"). **Before any LLM step** — steps 15–17 depend on this.

## Files

| File | Purpose |
|---|---|
| `app/migrations/003_llm_spend.sql` | `llm_spend` — the ledger the wrapper checks *before* calling, not just records into after |
| `app/research/budget.py` | `check_before_calling()`, `record_spend()`, `budgeted_call()` |
| `tests/test_budget.py` | R-075…R-079 |

## Design: why `budgeted_call()` exists on top of `check_before_calling()`

`check_before_calling()` raises `BudgetExceeded` — correct for R-075/076/077/
078's direct tests. But R-079 ("a breach degrades the panel only") needs a
caller-facing shape that *doesn't* propagate an exception up into a route
handler, since an unhandled exception is itself a crash, just a different
kind. `budgeted_call()` wraps the check, catches the breach, and returns a
`BudgetedResult(text=None, budget_exceeded=True, error_message="budget
reached for today")` — the shape a future `/research/*` route (step 15) can
render directly without a try/except of its own.

## What actually happened

All 5 tests passed on the first run.

## Acceptance criteria — closed

- [x] R-075…R-079 (`tests/test_budget.py`, all 5)

## Which docs this implements

`ARCHITECTURE.md` §6 (spend ceiling — caps mirrored from `app.config`).

## Requirement IDs closed

R-075, R-076, R-077, R-078, R-079.
