# 08 — Feed view (web)

`ARCHITECTURE.md` §8 step 08. Built together with step 09 (article view) since
both live in `app/web/routes.py` and share the FastAPI app object — tracked
separately because they close different requirement IDs.

## S-008 — a real Rule 6 contradiction, found and resolved

While wiring the article route, found `CLAUDE.md` Rule 6 ("never at click
time," stated unconditionally) genuinely contradicts `ARCHITECTURE.md` Flow B
and `EDITION-AND-UI.md`'s own front-page design, both of which explicitly
fetch on click for "show everything" (non-front-page) articles. Logged as
S-008: Rule 6 scopes to front-page (pre-fetched) articles; the two-tier
design's on-demand fetch for the rest is deliberate, not a violation. See
`logs/SESSIONS.md`.

## Three infrastructure bugs found and fixed while building this step

None were app-logic bugs — all were genuine conflicts between the test
harness (built at step 02, before any web code existed to expose them) and
real FastAPI/Windows/sqlite3 behavior:

1. **The network guard broke FastAPI's `TestClient` itself.** Windows'
   `asyncio` `ProactorEventLoop` (needed by every web test) creates a local
   `socket.socketpair()` for its internal self-pipe — pure local IPC, no
   network involved — but the guard patched `socket.socket()` construction
   outright, blocking that too. **Fixed:** rewrote the guard to patch the
   actual `connect()`/`create_connection()` calls, scoped to non-loopback
   addresses, leaving socket *construction* (and loopback connects) alone.
   `tests/conftest.py`.

2. **`sqlite3.ProgrammingError: SQLite objects created in a thread can only
   be used in that same thread.`** FastAPI dispatches sync route handlers to
   a worker threadpool; a `db_conn` fixture created in the pytest thread and
   handed to a route via `dependency_overrides` gets used from a different
   thread. **Fixed:** `check_same_thread=False` in `app/db.py`'s `connect()`
   — safe per `ARCHITECTURE.md` §10 (single writer, single reader process,
   never truly concurrent within one request).

3. **A test bug, not infra:** `test_render_sanitisation_only_removes_markup`
   used `str.index("a")` to check word order, which matched the "a" inside
   "ch**a**nge" before reaching the standalone word "a" later in the
   sentence — a substring collision with nothing to do with the sanitiser
   actually reordering text. Fixed with word-boundary tokenization
   (`re.findall(r"\w+", ...)` + subsequence check) instead of raw
   `.index()`.

## Files

| File | Purpose |
|---|---|
| `app/web/deps.py` | `get_db()` — FastAPI dependency, overridable in tests |
| `app/web/main.py` | The `FastAPI()` app object, static mount |
| `app/web/routes.py` | `/`, `/edition/{date}` (this step); `/article/*` (step 09) |
| `app/web/sanitize.py` | `sanitize_description()` — D-1's render-time tag-strip |
| `app/web/templates/*.html` | `base`, `index`, `_row_hero`, `_row_thumb`, `empty`, `article` |
| `app/web/static/app.css` | Hero/thumbnail `mask-image` fade per `EDITION-AND-UI.md` §6.4 (explicitly flagged there as "easy to get wrong") |
| `app/web/static/app.js` | Dwell tracking via `visibilitychange` + `sendBeacon` |
| `tests/test_feed_view.py` | R-054…R-058 |

## Verified live, not just in pytest

Started the real `uvicorn` server against a throwaway DB path, hit `/`,
`/static/app.css`, `/edition/2026-08-09` with `curl`. Confirmed: real HTTP
200s, static file serving works, and — with no edition built — the page
renders Rule 7's honest empty state ("No edition has been built yet") rather
than crashing or showing nothing. Cleaned up the throwaway DB after.

## Acceptance criteria — closed

- [x] R-054…R-058 (`tests/test_feed_view.py`, all 5)
- [x] R-003, R-010 (retroactive, `tests/test_rules.py` — R-010's `/research/*`
      half deferred to step 15, noted in the test's own docstring)

## Requirement IDs closed

R-003, R-010, R-054, R-055, R-056, R-057, R-058.
