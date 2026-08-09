# 05 — Rate limiter + fetcher

`ARCHITECTURE.md` §8 step 05, §2.4 (3-step fallback), §6 (shared limiter,
honest UA). D-3 (`logs/SESSIONS.md` S-006: robots disallow blocks Wayback too)
is structural here, not an afterthought.

## Files

| File | Purpose |
|---|---|
| `app/net/limiter.py` | `SharedLimiter` — injectable clock/sleep so tests verify the wait calculation without real sleeping. `default_limiter` — the one shared instance |
| `app/net/robots.py` | `is_allowed()` pure function (`urllib.robotparser`); `RobotsCache` — fetch-injected, per-domain, 1-day TTL |
| `app/extract/article.py` | Trafilatura wrapper. **Pinned call signature** (`include_images=True`, `output_format="markdown"`) — plan risk R-6: an unpinned signature makes "the extractor's output" an undefined moving target, which Rule 3's whole test depends on being well-defined |
| `app/net/fetcher.py` | `Fetcher.get_full_text()` — feed → live → Wayback. Exactly one path to the network (`_fetch`/`_wayback_lookup`, both always through the limiter) |
| `tests/test_fetcher.py` | R-033…R-041 |

## What actually happened

One real bug, caught immediately by the test run rather than by inspection:
two tests (`test_all_fetches_go_through_limiter`, `test_fallback_chain_order`)
fed raw text bytes to a fake "wayback fetch" response instead of real HTML.
Trafilatura correctly refused to extract anything from non-HTML bytes, so
both tests failed with `total_failure` instead of `wayback` — a **test** bug
(unrealistic fixture data), not an app bug. Fixed by wrapping the fake
response bodies in minimal real HTML (`<html><body><article>...`).

**D-3 structurally enforced, not just tested for:** `get_full_text()` checks
`robots_cache.is_fetch_allowed()` once, before either the live-fetch or
Wayback branch — there's no code path where robots-disallow reaches the live
fetch but not Wayback, or vice versa. `test_robots_disallow_blocks_wayback_too`
confirms the Wayback lookup function is never even called.

**Retroactively closed 3 more rule tests** written at step 03:
`test_stored_text_equals_extractor_output` (R-005, needed only the pinned
extractor), `test_rate_limiter_is_shared_and_enforced` (R-013),
`test_robots_txt_respected` (R-015) — neither of the latter two needed
anything beyond `app.net.limiter`/`app.net.robots` themselves.

## Acceptance criteria — closed

- [x] R-033…R-041 (`tests/test_fetcher.py`, all 9)
- [x] R-005, R-013, R-015 (retroactive, `tests/test_rules.py`)

## Which docs this implements

`ARCHITECTURE.md` §2.4, §5 (failure handling, incl. the D-3 patch), §6
(shared limiter, honest UA), §12.1 Rule 8 mapping.

## Requirement IDs closed

R-005, R-013, R-015, R-033, R-034, R-035, R-036, R-037, R-038, R-039, R-040, R-041.
