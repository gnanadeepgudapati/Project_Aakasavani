# 09 — Article view

`ARCHITECTURE.md` §8 step 09. Built together with step 08 — see that plan for
the three infrastructure bugs (network guard vs. TestClient, sqlite3
cross-thread access, a test word-order bug) found while building both.

Per `ARCHITECTURE.md` §8: **"Steps 01–09 are the product."** This is the last
of those — a finished, filterable edition that opens instantly. Everything
from step 10 onward is enhancement (`ROADMAP.md`: "ship 01-09, live with it
two weeks, then decide").

## Design

`GET /article/{hash}` follows Flow B exactly:

1. Already in `read`? Serve instantly, no write.
2. Else, `seen.full_text` populated (front-page, pre-fetched at 04:00)? Use
   it. **Zero network** — this is the path R-010 and R-059 both verify.
3. Else (a "show everything" article, never pre-fetched)? Fetch now, on
   click — S-008's deliberate exception, not a Rule 6 violation.
4. Either way, write a `read` row (Rule 9's `read_at`) and render.

`POST /article/{hash}/close` writes `dwell_seconds` — called by `app.js` on
`visibilitychange`, via `sendBeacon` so it fires reliably even as the tab
closes.

## Acceptance criteria — closed

- [x] R-059…R-061 (`tests/test_article_view.py`, all 3)
- [x] R-018 (retroactive, `tests/test_rules.py`)

## Which docs this implements

`ARCHITECTURE.md` Flow B, §8 step 09; `CLAUDE.md` Rule 9 (dwell logging).

## Requirement IDs closed

R-018, R-059, R-060, R-061.
