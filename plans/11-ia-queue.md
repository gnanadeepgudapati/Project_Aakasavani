# 11 — Internet Archive queue

`ARCHITECTURE.md` §8 step 11, §2.6, §4; `SOURCES.md` §4. No real IA
credentials exist (`BLOCKED.md` B-002 — free, but not yet obtained), and none
were needed: all four requirements are about queueing structure and rate
discipline, fully testable against a fake `save_fn`.

## Files

| File | Purpose |
|---|---|
| `app/ia/queue.py` | `enqueue()`, `enqueue_front_page()`, `drain_queue()` |
| `tests/test_ia.py` | R-065…R-068 |

## Design: "never blocks a request" is structural, not a promise

`enqueue()` is a single fast `INSERT`. `drain_queue()` — the only function
that ever calls `save_fn`, the slow (10-60s per `ARCHITECTURE.md` §2.6),
network-touching operation — is a separate function nothing on the read/build
path calls directly. R-068 doesn't test a timing budget; it tests that this
separation actually holds, by patching `save_fn` to explode and confirming
`enqueue()` alone never triggers it.

## What actually happened

All 4 tests passed on the first run — the design was straightforward given
the fetcher/limiter patterns already established at step 05.

## Acceptance criteria — closed

- [x] R-065 `test_ia.py::test_front_page_enqueued`
- [x] R-066 `test_ia.py::test_rate_six_per_minute`
- [x] R-067 `test_ia.py::test_retries_thrice_then_abandons`
- [x] R-068 `test_ia.py::test_never_blocks_request`

## Which docs this implements

`ARCHITECTURE.md` §2.6, §4 Flow B ("INSERT ia_queue — async, fire and
forget"); `EDITION-AND-UI.md` §1.2 (04:30 queue step); `SOURCES.md` §4.

## Requirement IDs closed

R-065, R-066, R-067, R-068.
