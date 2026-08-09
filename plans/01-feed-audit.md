# 01 — Feed audit

**Not code.** `ARCHITECTURE.md` §8 step 01: fetch each of the 35 frozen feeds
(`SOURCES.md` §1) once, record which ship `<content:encoded>`, and produce the
registry every later step reads from.

## Files

| File | Purpose |
|---|---|
| `data/feeds.yaml` | **New.** The 35 frozen feeds — url, name, section, source_weight, has_full_text. Source of truth; `feeds` table (step 04) loads from this, not the reverse |
| `scripts/audit_feeds.py` | **New.** Fetches each feed once, writes `has_full_text` + basic health back into `feeds.yaml` |
| `pyproject.toml` | **New.** Deps needed starting now: `feedparser`, `pyyaml`, `pytest`. (`trafilatura`, `fastapi` etc. deferred to the steps that need them) |
| `.env.example` | **New.** Documents `BLOCKED.md` B-002's variables. Empty values, committed |
| `tests/test_registry.py` | **New.** R-020…R-023 |

## Section assignment (S-001, closed)

Per `logs/SESSIONS.md` S-001: `section ∈ {tech, finance, world_india}`, applied
per-feed using subject matter, not the outlet's country. The finance-flavoured
Indian outlets go to `finance`:

| SOURCES.md group | → section | Count |
|---|---|---|
| World (all 7) | `world_india` | 7 |
| Tech (all 8) | `tech` | 8 |
| Finance (all 4) | `finance` | 4 |
| India — Hindu sci-tech | `tech` | 1 |
| India — Hindu business, Livemint markets, Livemint companies, Business Standard, Economic Times | `finance` | 5 |
| India — everything else (10 feeds) | `world_india` | 10 |

Totals: `tech` 9, `finance` 9, `world_india` 17 — 35 total. Matches the counts
already recorded in `EDITION-AND-UI.md` §2.1 and `logs/SESSIONS.md` S-001.

`source_weight` starts at **3** (the schema default) for all 35. Per
`EDITION-AND-UI.md`'s DECIDED block: "Hand-edit the source weights when the
front page looks wrong" — there's no front page yet to look wrong, so tuning
happens after step 07, not now.

## Acceptance criteria — named as the tests that will exist

- [ ] R-020 `test_registry.py::test_registry_matches_frozen_list` — registry has
      exactly the 35 URLs in `SOURCES.md` §1, no more, no fewer
- [ ] R-021 `test_registry.py::test_every_feed_has_section_and_weight` — every
      entry has `section ∈ {tech,finance,world_india}` and `1 ≤ source_weight ≤ 5`
- [ ] R-022 `test_registry.py::test_has_full_text_recorded_for_every_feed` —
      `has_full_text` is `true`/`false` (not `null`) for every entry after audit
- [ ] R-023 `test_registry.py::test_no_google_news_redirect_sources` — no
      `news.google.com` URL present (R-12: dead code, no frozen feed uses it)

## Red-first

Write `tests/test_registry.py` against a `data/feeds.yaml` that does not exist
yet. Expected failure: `FileNotFoundError`, not an import error or typo. Then
create the file and run `scripts/audit_feeds.py` against the real internet
(the one script besides `test_live.py` and `record_fixtures.py` permitted to
touch the network) to fill in `has_full_text`. Re-run — expect green.

## Politeness, even for a one-time manual script

Rule 8 doesn't stop applying just because this isn't the scheduled build.
`audit_feeds.py`: honest UA (`ARCHITECTURE.md` §6 string), ~1 req/sec spacing,
no retries beyond a single timeout-triggered retry, no concurrency.

## Which docs this implements

`ARCHITECTURE.md` §8 step 01, §2.1 ("populates `feeds`... single highest-value
thing to check per feed"), §6 (User-Agent string); `SOURCES.md` §1 (the frozen
list itself); `EDITION-AND-UI.md` §2.1 (section assignment, post-S-001).

## Requirement IDs closed

R-020, R-021, R-022, R-023.
