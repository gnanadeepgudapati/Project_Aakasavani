# 02 — Fixtures + test harness

`ARCHITECTURE.md` §12.2. The oracle, part 1. Written to match what was actually
built (the user authorized continuous building without per-step approval
gates, so this plan is a record of the step, not a pre-approval document).

## Files

| File | Purpose |
|---|---|
| `app/clock.py` | Injectable `now()`. `freeze()`/`unfreeze()` for tests. Nothing else in `app/` may call `datetime.now()` directly |
| `tests/conftest.py` | Autouse network guard (patches `socket.socket`/`create_connection` per-test), `frozen_clock`, `temp_db_path`, `db_conn` (lazy-imports `app.db`, step 04), `fixtures_dir` |
| `tests/__init__.py` | Makes `tests` a real package — needed so `tests.conftest.NetworkAccessError` is the same class object a test imports and the one the guard raises. Pytest's default "prepend" import mode loads a bare `conftest.py` as a top-level module otherwise, which silently breaks `pytest.raises(SomeClassFromConftest)` |
| `tests/test_harness.py` | R-024…R-027 |
| `scripts/record_fixtures.py` | The one script (besides `audit_feeds.py`) allowed to touch the network. Regenerates CAPTURED fixtures |
| `fixtures/PROVENANCE.md` | Which fixtures are captured/derived/hand-authored, and why |
| `fixtures/{feeds,articles,gdelt,wayback,robots}/*` | 15 files — see `PROVENANCE.md` |

## What actually happened, vs. the plan

**GDELT capture failed.** `scripts/record_fixtures.py` hit `HTTP 429` from the
real DOC 2.0 endpoint on the first request, and again after a 15s backoff.
Per Rule 8, did not retry further or work around it. `gdelt/artlist.json` is
hand-authored from the documented shape in `SOURCES.md` §2 instead — recorded
honestly in `PROVENANCE.md`, not silently swapped for a live one.

**Wayback needed a URL swap to get a real "hit".** `simonwillison.net` and
`bbc.com/news` both returned empty `archived_snapshots` — plausible (a specific
timestamp query, or a URL Wayback indexes differently than expected) rather
than a service failure. Used a Wikipedia article URL instead, which has deep,
reliable archive history. The empty response encountered along the way became
the (real, observed) basis for `available_miss.json`.

**Captured feeds were trimmed post-capture**, not size-limited at fetch time —
`record_fixtures.py` saves the raw response, then a one-off trim (not
committed as reusable script logic, since it's a one-time operation on a
specific capture) cut both feed fixtures from 20 items to 5, verified still
parseable and still exhibiting the property they're named for
(`has_full_text` true/false) after trimming.

## Acceptance criteria — closed

- [x] R-024 `test_harness.py::test_network_access_raises` — genuinely attempted
      a real `socket.socket()` and `socket.create_connection()` call, confirmed
      both raise `NetworkAccessError`
- [x] R-025 `test_harness.py::test_clock_is_frozen` — frozen clock doesn't
      advance between calls, and re-freezing to simulate elapsed time works
- [x] R-026 `test_harness.py::test_db_is_temporary` — path is under `tmp_path`,
      distinct from the real `aakasavani.db`, not created by the fixture itself
- [x] R-027 `test_harness.py::test_all_fixtures_present` — all 15 fixture files
      exist and are non-empty

## Which docs this implements

`ARCHITECTURE.md` §12.2 (fixtures, `conftest.py` guarantees), §12.3
(red-first — demonstrated for R-024: the guard was proven to actually block a
real connection, not just assumed to). `plans/00-implementation-plan.md` §5
(fixture provenance categories).

## Requirement IDs closed

R-024, R-025, R-026, R-027.
