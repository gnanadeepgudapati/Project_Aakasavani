# 23 — Feed registry sync + poll hardening

`plans/00b-real-data-and-ui-plan.md` Track A step 23. Fixes D-1…D-5.
`ARCHITECTURE.md` §2.1 (conditional GET, per-domain politeness), §5 (failure
handling — disable after 10 consecutive fails), §6 (shared limiter, no
bypass).

## The gap

`poll_all_feeds` (`app/edition/build.py`) reads from the `feeds` **table**,
but nothing ever wrote `data/feeds.yaml` into that table (D-1) — every real
run polls zero feeds, silently. One dead feed raising an exception kills the
whole build (D-2) — 7/35 frozen feeds are currently dead
(`BLOCKED.md` B-004), so this is the common case, not the exception.
Conditional GET is unimplemented (D-4): `feeds.etag`/`last_modified` exist as
columns and are never read or written. `fail_count`/`enabled` are never
updated (D-5). And `poll_all_feeds` imports `_default_http_get` directly,
never calling `limiter.acquire()` — a live Rule 8 violation on the real path
(D-3), even though `test_all_fetches_go_through_limiter` (R-034) proves the
*article*-fetch path is fine; nothing ever tested the *feed*-poll path.

## Design

### `app/registry.py::sync_feeds_to_db(conn, path=FEEDS_YAML_PATH)`

Upserts every `feeds.yaml` entry into `feeds`, keyed by `url`. For an
existing row: updates `name`/`section`/`source_weight`/`has_full_text` only —
**never touches `etag`, `last_modified`, `fail_count`, `enabled`**, since
those are poll *state*, not registry *data*, and a naive delete+reinsert
would erase 30 days of conditional-GET history and un-disable every feed
that had earned `enabled=0` the hard way. Idempotent by construction (a
second call with the same YAML changes nothing). Rows whose URL has been
*removed* from the YAML are left alone, not deleted — the frozen list only
grows or gets explicitly retired via a SESSIONS entry, never silently
vanishes from a poll's perspective.

### `poll_all_feeds` — conditional GET + per-feed isolation

New return-value shape for the injected `fetch_fn`: instead of
`fetch_fn(url) -> bytes`, it becomes
`fetch_fn(url, etag, last_modified) -> FeedFetchResult(status, body, etag,
last_modified)` (`app/net/fetcher.py`). The default (`_default_feed_fetch`)
sends `If-None-Match`/`If-Modified-Since` when the stored values are
present, routes through `app.net.limiter.default_limiter.acquire(domain)`
**before** the request (the D-3 fix), and treats HTTP 304 as a normal
return value, not an exception — everything else non-2xx propagates as an
exception for the per-feed `try/except` to catch.

`poll_all_feeds` wraps each feed's fetch+parse+insert in `try/except`:

- success (200, parsed, inserted) → `fail_count = 0`, `etag`/`last_modified`
  updated from the response, `last_polled` updated
- success (304) → same, but `etag`/`last_modified` unchanged (nothing new
  to store) and zero rows inserted for this feed — **not** a failure
- any exception → `fail_count += 1`, `last_polled` updated, `enabled = 0`
  once `fail_count >= 10`; loop continues to the next feed regardless

The only existing test with an incompatible `fetch_fn` shape is
`tests/test_topup.py` (2 call sites) — updated to return `FeedFetchResult`
instead of raw `bytes`, same assertions.

### New rule test — D-3, Rule 8

`test_feed_polling_routes_through_shared_limiter` in `tests/test_rules.py`:
calls `poll_all_feeds(conn)` with **no** `fetch_fn` injected (i.e. exercises
the real default wiring, not a test double), monkeypatching only
`urllib.request.urlopen` — the actual module-level `default_limiter` is
spied on but otherwise real. This is the test that would have caught D-3:
`test_all_fetches_go_through_limiter` (R-034) only ever exercised
`Fetcher`, never `poll_all_feeds`.

## Files

| File | Change |
|---|---|
| `app/registry.py` | `sync_feeds_to_db()` |
| `app/net/fetcher.py` | `FeedFetchResult`, `_default_feed_fetch()` |
| `app/edition/build.py` | `poll_all_feeds()` rewritten: conditional GET, per-feed try/except, fail_count/enabled/last_polled bookkeeping |
| `tests/test_registry.py` | new tests for `sync_feeds_to_db` |
| `tests/test_edition.py` | new tests for poll hardening |
| `tests/test_topup.py` | 2 call sites adapted to the new `fetch_fn` contract |
| `tests/test_rules.py` | 1 new Rule 8 test (append-only) |

## Acceptance criteria (red first)

- R-089 `sync_feeds_to_db` inserts every YAML entry as a new `feeds` row
- R-090 `sync_feeds_to_db` preserves `etag`/`last_modified`/`fail_count`/`enabled` on rows that already exist, and is idempotent
- R-091 a feed whose fetch raises does not abort the poll — other feeds are still processed
- R-092 a failing feed's `fail_count` increments; a succeeding feed's resets to 0
- R-093 a feed is disabled (`enabled = 0`) once `fail_count` reaches 10, and a disabled feed is not polled again
- R-094 the default feed fetch sends `If-None-Match`/`If-Modified-Since` HTTP headers from the stored values (fetcher-level)
- R-095 `poll_all_feeds` passes the stored `etag`/`last_modified` into `fetch_fn` and updates them from a 200 response (integration)
- R-096 HTTP 304 is treated as success — no new rows, no failure, stored `etag`/`last_modified` unchanged, `last_polled` updated
- R-097 feed polling's real default path routes every request through the shared limiter (Rule 8 rule test)

## Which docs this implements

`ARCHITECTURE.md` §2.1 (conditional GET, per-domain politeness), §5 (fail_count/disable-at-10), §6 (shared limiter, no bypass).

## What actually happened

All 9 new tests passed on first implementation after red-first confirmation.
One incidental discovery: the only pre-existing test with an incompatible
`fetch_fn` contract was `tests/test_topup.py` (2 call sites) - updated from
`fetch_fn(url) -> bytes` to `fetch_fn(url, etag, last_modified) ->
FeedFetchResult`, same assertions, confirmed red (`TypeError` swallowed by
the new per-feed `try/except`, silently producing `inserted == 0` — itself
a live demonstration that D-2's isolation works) before the fix.

`FAIL_COUNT_DISABLE_THRESHOLD` uses `>=` rather than `==` 10, deliberately,
in case a row's `fail_count` is ever bumped past 10 by something else later.

## Requirement IDs closed

R-089, R-090, R-091, R-092, R-093, R-094, R-095, R-096, R-097.
