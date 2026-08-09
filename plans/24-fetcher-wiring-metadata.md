# 24 — Fetcher wiring + metadata completeness

`plans/00b-real-data-and-ui-plan.md` Track A step 24. Fixes D-6…D-8.
`ARCHITECTURE.md` §2.4 (3-step fallback), §6 (shared limiter, robots.txt
cached 1 day), `EDITION-AND-UI.md` §6 (images).

## The gap

`prefetch_front_page` (`app/edition/build.py:63`) constructed a bare
`Fetcher()` — `robots_cache` defaults to `None`, and `Fetcher.get_full_text`
only checks robots when `robots_cache is not None`. The check's *logic* was
correct and unit-tested (`test_fetcher.py` injects `robots_cache=` directly),
but production never passed one — a silent Rule 8 gap on the one path that
actually runs unattended every night (D-6). Separately, `resolve_description`
already supports an `og:description`/`twitter:description` tier via
`page_html`, but nothing extracts `og:image`, so images come only from RSS
`media:*` tags — many feeds ship none (D-7). And `atomic_swap` accepts
`read_minutes` but `run_build` never computes or passes it (D-8).

## Design

### D-6 — real `RobotsCache`, wired by default

`app/net/fetcher.py` gains `_default_robots_fetch(domain)` — fetches
`https://{domain}/robots.txt` through `default_limiter`, honest UA, returns
`None` on any failure (permissive, per common practice, matching
`RobotsCache`'s existing contract) — and `default_fetcher()`, a factory that
builds a `RobotsCache(fetch_fn=_default_robots_fetch, clock=time.time)`
(1-day TTL is `RobotsCache`'s own `ONE_DAY_SECONDS`, unchanged) and returns
`Fetcher(robots_cache=robots_cache)`. `prefetch_front_page` changes
`fetcher = fetcher or Fetcher()` to `fetcher = fetcher or default_fetcher()`.

New rule test (already written and red at the end of step 23, since it
exercises this step's code): `test_real_build_path_respects_robots_txt` in
`tests/test_rules.py` — calls `prefetch_front_page` with **no** fetcher
injected, monkeypatches `_default_robots_fetch` to a disallow-everything
robots.txt and `urllib.request.urlopen` to fail the test if the article
fetch is even attempted, proving the *production* default enforces robots,
not just a hand-built `Fetcher` in a unit test.

### D-7 — `og:image` from page bytes already in hand

`FetchResult` gains `page_html: bytes | None = None`, populated by
`Fetcher.get_full_text` only on the steps that actually fetch a page (live
fetch / Wayback) — the `feed` (`content:encoded`) tier never touches the
network, so there is no page to extract from there, correctly. `app.ingest.
parser` gains `extract_og_image(page_html)`, reusing the existing
`_meta_content` helper (`property="og:image"`) rather than a new regex.
`prefetch_front_page`: when the feed gave no `image_url` and `page_html` is
present, extract and `UPDATE seen.image_url`. **No extra HTTP request** —
this is the same bytes already fetched for Trafilatura.

### D-8 — `read_minutes`

`prefetch_front_page` returns the total word count summed across every
successfully pre-fetched article (it already loops over every row's
`result.text`). `run_build` computes `ceil(total_words / 220)` and passes it
to `atomic_swap` as `read_minutes`.

## Files

| File | Change |
|---|---|
| `app/net/fetcher.py` | `_default_robots_fetch()`, `default_fetcher()`; `FetchResult.page_html` |
| `app/ingest/parser.py` | `extract_og_image()` |
| `app/edition/build.py` | `prefetch_front_page` uses `default_fetcher()`, extracts `og:image`, returns word count; `run_build` computes `read_minutes` |
| `tests/test_fetcher.py` | new tests for `default_fetcher`/`_default_robots_fetch`, `FetchResult.page_html` |
| `tests/test_parser.py` | new test for `extract_og_image` |
| `tests/test_edition.py` | new tests for `og:image` population and `read_minutes` |
| `tests/test_rules.py` | 1 new Rule 8 test (already written at the end of step 23, red until this step) |

## Acceptance criteria (red first)

- R-098 `default_fetcher()` returns a `Fetcher` with a non-`None` `robots_cache`
- R-099 `_default_robots_fetch` routes through the shared limiter
- R-100 the real build path (`prefetch_front_page`, no fetcher injected) blocks on `robots.txt` disallow (Rule 8 rule test — written at end of step 23)
- R-101 `og:image` extracted from already-fetched page bytes populates `seen.image_url` only when the feed provided none, with no extra HTTP request
- R-102 `read_minutes = ceil(total_words / 220)` computed across the edition and stored on `editions.read_minutes`

## Which docs this implements

`ARCHITECTURE.md` §2.4, §6 (robots cache, shared limiter), `EDITION-AND-UI.md` §6 (images).

## What actually happened

`test_real_build_path_respects_robots_txt` (R-100) was written at the tail
end of step 23 (it needed step 24's not-yet-built `_default_robots_fetch`
to even monkeypatch) and confirmed red for the right reason
(`AttributeError: ... has no attribute '_default_robots_fetch'`) before
this step's code existed - then, after `_default_robots_fetch`/
`default_fetcher` existed but `build.py` still constructed a bare
`Fetcher()`, re-confirmed red for a *different*, now-correct reason (the
real Wayback lookup path got reached and the monkeypatched `urlopen` raised
the intentional `AssertionError`). Wiring `default_fetcher()` into
`prefetch_front_page` turned it green.

All other new tests (`test_default_fetcher_has_a_real_robots_cache`,
`test_default_robots_fetch_routes_through_shared_limiter`,
`test_fetch_result_carries_page_html_for_live_and_wayback_only`,
`test_extract_og_image`, `test_og_image_populated_only_when_feed_gave_
none`, `test_read_minutes_computed_from_prefetched_word_count`) passed on
first implementation.

One design note worth recording: `og:image` extraction only fills a gap -
it never overwrites a feed-provided `image_url`, tested explicitly
(`test_og_image_populated_only_when_feed_gave_none`) since the plan's
wording ("populate `seen.image_url` when the feed provided none") could
otherwise be misread as "always overwrite from the page".

## Requirement IDs closed

R-098, R-099, R-100, R-101, R-102.
