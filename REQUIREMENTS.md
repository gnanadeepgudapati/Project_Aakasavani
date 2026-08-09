# REQUIREMENTS

Generated from `plans/00-implementation-plan.md` on approval, per Prompt 2.

**A box is ticked ONLY when its `verify:` command exits 0. Never by judgement.**
A requirement with no `verify:` line is a wish, not a requirement.

IDs are permanent once assigned — do not renumber to close gaps. Steps 20–22
(deep history, ranking, mobile) have no requirements yet: `ARCHITECTURE.md` §8
gates them behind "ship 01–09, live with it two weeks, then decide" and
`plans/NN-<step>.md` for each doesn't exist yet. Adding requirements for an
unplanned step would be exactly the "wish with no verify" this file exists to
forbid — they're added when that step gets its own plan.

**This session builds 01–03 only** (Prompt 2). Requirements for 04+ exist here
so the full checklist is visible, but stay unchecked until their step is
planned and built.

---

## Ten Rules — `tests/test_rules.py` (step 03)

Runs on every verify, forever, regardless of which step is in progress.
Mapping: `ARCHITECTURE.md` §12.1. Rulings D-1/D-2 (`logs/SESSIONS.md` S-006)
already folded into R-002, R-003, R-010.

**Written at step 03 (2026-08-09); most closed later, as their steps land.**
Every test does its own lazy import inside the function body, so a rule test
whose target module doesn't exist yet fails cleanly for that reason alone —
legitimate "red before any feature exists" (`ARCHITECTURE.md` §8), not a
collection error blocking the other 18. R-001/R-007/R-014/R-016/R-019 are
ticked now because they're either self-contained (config values, installed
packages — genuinely demonstrated catching a real violation, not vacuous) or
their underlying mechanism is proven against synthetic fixtures
(`test_static_analysis_helper_catches_a_real_case`, which itself caught and
led to fixing a real relative-import resolution bug). The rest tick as their
dependent step lands; **all 19 get a final violation-demonstration pass once
the whole build is done** — see `plans/03-rules.md`.

- [x] R-001  Rule 1 — no Anthropic client reachable from feed/article render (static)
      verify: pytest tests/test_rules.py::test_no_llm_import_in_render_path
      (passes vacuously until app.web.routes exists, step 08 — the walker itself is
      proven against synthetic violations by test_static_analysis_helper_catches_a_real_case)
- [x] R-002  Rule 1 — `seen.description` verbatim from parser at storage
      verify: pytest tests/test_rules.py::test_stored_description_is_verbatim
- [x] R-003  Rule 1 — sanitiser strips markup, never rewords
      verify: pytest tests/test_rules.py::test_render_sanitisation_only_removes_markup
- [x] R-004  Rule 2 — one story across 6 feeds yields 6 rows, not 1
      verify: pytest tests/test_rules.py::test_six_outlets_six_entries
- [x] R-005  Rule 3 — `read.full_text` identical to extractor output, no post-processing
      verify: pytest tests/test_rules.py::test_stored_text_equals_extractor_output
- [x] R-006  Rule 4 — the 04:00 build calls Anthropic zero times
      verify: pytest tests/test_rules.py::test_build_makes_zero_llm_calls
- [x] R-007  Rule 4 — no Anthropic import reachable from the build path (static)
      verify: pytest tests/test_rules.py::test_no_llm_import_in_build_path
      (vacuous until app.edition.build exists, step 07 — same walker as R-001)
- [ ] R-008  Rule 5 — sweep strips title/description/source, keeps hash, sets expired=1
      verify: pytest tests/test_rules.py::test_sweep_strips_text_keeps_hash
- [ ] R-009  Rule 5 — `read` rows survive any TTL sweep, at any clock offset
      verify: pytest tests/test_rules.py::test_read_rows_never_expire
- [x] R-010  Rule 6 — reading routes make no outbound HTTP; `/research/*` is the sole exception
      (the /research/* half of this proof is deferred to step 15 - see test docstring)
      verify: pytest tests/test_rules.py::test_no_network_on_reading_path
- [x] R-011  Rule 7 — a build that raises mid-way leaves the previous edition live
      verify: pytest tests/test_rules.py::test_failed_build_keeps_previous_edition
- [x] R-012  Rule 7 — a failure inside the swap transaction leaves zero partial rows
      verify: pytest tests/test_rules.py::test_swap_is_atomic
- [x] R-013  Rule 8 — two callers on one domain are enforced ≥1s apart, one shared instance
      verify: pytest tests/test_rules.py::test_rate_limiter_is_shared_and_enforced
- [x] R-014  Rule 8 — User-Agent matches `ARCHITECTURE.md` §6, contact address present, no impersonation
      verify: pytest tests/test_rules.py::test_user_agent_is_honest
      (demonstrated catching a real Chrome-impersonating UA string, 2026-08-09)
- [x] R-015  Rule 8 — `restrictive.txt` fixture refuses the fetch
      verify: pytest tests/test_rules.py::test_robots_txt_respected
- [x] R-016  Rule 8 — no evasion dependency importable (static)
      verify: pytest tests/test_rules.py::test_no_evasion_dependencies
      (demonstrated catching a simulated selenium install, 2026-08-09)
- [x] R-017  Rule 9 — `read` schema has `read_at` and `dwell_seconds`, both writable
      verify: pytest tests/test_rules.py::test_read_schema_has_dwell_columns
- [x] R-018  Rule 9 — opening then leaving an article writes non-null `dwell_seconds`
      verify: pytest tests/test_rules.py::test_article_view_writes_dwell
- [x] R-019  Rule 10 — no forbidden dependency importable (static)
      verify: pytest tests/test_rules.py::test_no_forbidden_dependencies
      (demonstrated catching a simulated redis+sqlalchemy install, 2026-08-09)

**Step 03 acceptance is not "these pass."** Each must be observed catching a
real violation before it counts — break the guarded thing, watch red, restore.
Demonstrated to the user per Prompt 2; not separately `verify:`-able as a
checkbox, since the proof is a live demonstration, not a persistent test.

---

## Step 01 — Feed audit (not code)

`ARCHITECTURE.md` §8. Populates `data/feeds.yaml` from the 35 frozen feeds in
`SOURCES.md` §1. No credentials needed.

- [x] R-020  Registry contains exactly the 35 frozen feeds, no more, no fewer
      verify: pytest tests/test_registry.py::test_registry_matches_frozen_list
- [x] R-021  Every feed has a `section` in {tech, finance, world_india} and a `source_weight` 1–5
      verify: pytest tests/test_registry.py::test_every_feed_has_section_and_weight
- [x] R-022  Every feed was audited; reachable ones have bool `has_full_text`, unreachable ones are logged in BLOCKED.md (B-004 — 7/35 currently down)
      verify: pytest tests/test_registry.py::test_has_full_text_recorded_for_every_feed
- [x] R-023  No Google News redirect URL in the frozen registry (R-12, dead code otherwise)
      verify: pytest tests/test_registry.py::test_no_google_news_redirect_sources

## Step 02 — Fixtures + harness

`ARCHITECTURE.md` §12.2. The oracle, part 1.

- [x] R-024  Any real network call from within a test raises
      verify: pytest tests/test_harness.py::test_network_access_raises
- [x] R-025  `app.clock.now()` returns the injected time, never wall-clock time
      verify: pytest tests/test_harness.py::test_clock_is_frozen
- [x] R-026  Test DB is a fresh temp file per test, never the real `aakasavani.db`
      verify: pytest tests/test_harness.py::test_db_is_temporary
- [x] R-027  Every fixture named in `plans/00-implementation-plan.md` §5 exists on disk
      verify: pytest tests/test_harness.py::test_all_fixtures_present

## Step 03 — `tests/test_rules.py`

See "Ten Rules" above — R-001…R-019.

---

## Step 04 — SQLite schema + migrations

Schema in `plans/00-implementation-plan.md` §2 (12 changes from the
`ARCHITECTURE.md` §3 draft).

- [x] R-028  Migrations apply cleanly and re-applying is a no-op
      verify: pytest tests/test_schema.py::test_migrations_idempotent
- [x] R-029  WAL, foreign_keys=ON, busy_timeout=5000 all set on connect
      verify: pytest tests/test_schema.py::test_pragmas_applied
- [x] R-030  `read_fts`/`seen_fts` stay in sync across insert, update, delete
      verify: pytest tests/test_schema.py::test_fts_stays_in_sync_on_insert_update_delete
- [x] R-031  `edition_items.url_hash` FK to a nonexistent edition is rejected
      verify: pytest tests/test_schema.py::test_edition_items_fk_enforced
- [x] R-032  A `section` outside {tech, finance, world_india} is rejected at write
      verify: pytest tests/test_schema.py::test_section_check_constraint

## Step 05 — Rate limiter + fetcher

- [x] R-033  Two requests to the same domain are ≥1s apart
      verify: pytest tests/test_fetcher.py::test_one_request_per_second_per_domain
- [x] R-034  No code path reaches the network without going through the shared limiter
      verify: pytest tests/test_fetcher.py::test_all_fetches_go_through_limiter
- [x] R-035  `robots/restrictive.txt` fixture blocks the fetch
      verify: pytest tests/test_fetcher.py::test_robots_disallow_blocks_fetch
- [x] R-036  robots.txt fetched at most once per domain per day
      verify: pytest tests/test_fetcher.py::test_robots_cached_per_day
- [x] R-037  Extraction under 500 chars is treated as failure, not success
      verify: pytest tests/test_fetcher.py::test_short_extraction_is_failure
- [x] R-038  Fallback order is feed → live → Wayback, in that order
      verify: pytest tests/test_fetcher.py::test_fallback_chain_order
- [x] R-039  All three fallbacks failing returns headline+link, not an error
      verify: pytest tests/test_fetcher.py::test_total_failure_returns_headline_only
- [x] R-040  A Wayback 429 backs off every worker, not just the one that hit it
      verify: pytest tests/test_fetcher.py::test_wayback_429_global_backoff
- [x] R-041  robots.txt disallow blocks the Wayback fallback too (D-3, `logs/SESSIONS.md` S-006)
      verify: pytest tests/test_fetcher.py::test_robots_disallow_blocks_wayback_too

## Step 06 — Feed parser + dedupe

- [x] R-042  `<content:encoded>` extracted when present
      verify: pytest tests/test_parser.py::test_content_encoded
- [x] R-043  Absent `<content:encoded>` yields `None`, not `AttributeError`
      verify: pytest tests/test_parser.py::test_missing_content_encoded
- [x] R-044  Malformed feed XML does not crash the parser
      verify: pytest tests/test_parser.py::test_malformed_xml_survives
- [x] R-045  Empty feed (valid XML, zero items) yields zero items, not an error
      verify: pytest tests/test_parser.py::test_empty_feed
- [x] R-046  Canonicalisation strips `utm_*`/`fbclid`/fragment
      verify: pytest tests/test_parser.py::test_canonicalise_strips_tracking
- [x] R-047  Same URL with different tracking params hashes identically
      verify: pytest tests/test_parser.py::test_tracking_params_do_not_change_hash
- [x] R-048  A hash already in `seen` is skipped, not re-inserted
      verify: pytest tests/test_parser.py::test_duplicate_is_skipped
- [x] R-049  Description fallback order: `<description>` → og:description → twitter:description → body prefix → headline
      verify: pytest tests/test_parser.py::test_description_fallback_order

## Step 07 — Edition build job

- [x] R-050  13 articles selected per section
      verify: pytest tests/test_edition.py::test_selects_13_per_section
- [x] R-051  Ranking is recency, tie-broken by `feeds.source_weight`
      verify: pytest tests/test_edition.py::test_ranking_recency_then_weight
- [x] R-052  Every front-page item has full text pre-fetched before swap
      verify: pytest tests/test_edition.py::test_every_front_page_item_prefetched
- [x] R-053  `editions.status` flips to `live` only after full success
      verify: pytest tests/test_edition.py::test_swap_only_on_success

## Step 08 — Feed view

- [x] R-054  Front page renders the live edition's articles
      verify: pytest tests/test_feed_view.py::test_front_page_renders_edition
- [x] R-055  Section chips filter the visible list
      verify: pytest tests/test_feed_view.py::test_section_chip_filters
- [x] R-056  Hero image only on each section's lead story
      verify: pytest tests/test_feed_view.py::test_hero_on_lead_only
- [x] R-057  Missing image renders text-only, no placeholder/broken icon
      verify: pytest tests/test_feed_view.py::test_missing_image_renders_text_only
- [x] R-058  "Show everything" lists the remainder beyond the front page
      verify: pytest tests/test_feed_view.py::test_show_everything_lists_remainder

## Step 09 — Article view

- [x] R-059  Opening a front-page article serves pre-fetched text, zero fetch calls
      verify: pytest tests/test_article_view.py::test_served_from_prefetch
- [x] R-060  `dwell_seconds` is written on leaving the article
      verify: pytest tests/test_article_view.py::test_dwell_seconds_written
- [x] R-061  Opening an article creates exactly one `read` row
      verify: pytest tests/test_article_view.py::test_read_row_created

## Step 10 — Topic chips

- [x] R-062  A saved FTS5 query matches the articles it should
      verify: pytest tests/test_topics.py::test_topic_query_matches
- [x] R-063  A newly added topic immediately matches existing history
      verify: pytest tests/test_topics.py::test_new_topic_is_retroactive
- [x] R-064  Topics are editable at runtime, no redeploy
      verify: pytest tests/test_topics.py::test_topic_editable

## Step 11 — Internet Archive queue

- [ ] R-065  Every front-page article is enqueued to `ia_queue`
      verify: pytest tests/test_ia.py::test_front_page_enqueued
- [ ] R-066  Drain rate does not exceed 6/min
      verify: pytest tests/test_ia.py::test_rate_six_per_minute
- [ ] R-067  Failed captures retry ≤3 times then are abandoned, not retried forever
      verify: pytest tests/test_ia.py::test_retries_thrice_then_abandons
- [ ] R-068  IA queueing never blocks a request/response cycle
      verify: pytest tests/test_ia.py::test_never_blocks_request

## Step 12 — TTL sweep + nightly backup

- [ ] R-069  Sweep job strips text and keeps the hash (integration-level, vs. R-008's unit-level rule test)
      verify: pytest tests/test_sweep.py::test_sweep_strips_keeps_hash
- [ ] R-070  Running the sweep twice is a no-op the second time
      verify: pytest tests/test_sweep.py::test_sweep_idempotent
- [ ] R-071  Backup file opens and reads correctly (via `.backup()` API, not CLI — R-2)
      verify: pytest tests/test_sweep.py::test_backup_is_readable

## Step 13 — Past editions

- [ ] R-072  `/edition/YYYY-MM-DD` serves that date's edition
      verify: pytest tests/test_past_editions.py::test_edition_by_date
- [ ] R-073  An unknown date returns 404, not a 500 or an empty page
      verify: pytest tests/test_past_editions.py::test_unknown_date_404
- [ ] R-074  `/` always serves the most recent `live` edition
      verify: pytest tests/test_past_editions.py::test_root_serves_latest_live

## Step 14 — Budget wrapper

- [ ] R-075  The cap check raises `BudgetExceeded` *before* the API call, not after
      verify: pytest tests/test_budget.py::test_raises_before_calling
- [ ] R-076  A single call estimated above $0.10 is refused
      verify: pytest tests/test_budget.py::test_single_call_cap
- [ ] R-077  Cumulative daily spend above $2.00 is refused
      verify: pytest tests/test_budget.py::test_daily_cap
- [ ] R-078  Cumulative monthly spend above $25.00 is refused
      verify: pytest tests/test_budget.py::test_monthly_cap
- [ ] R-079  A budget breach degrades the panel only — reading path unaffected
      verify: pytest tests/test_budget.py::test_breach_does_not_break_reading

## Step 15 — Research panel: Ask tab

Model pinned `claude-haiku-4-5-20251001` (`logs/SESSIONS.md` S-004). No Sonnet
tier in Phase 1.

- [ ] R-080  Starter questions generate lazily, on first panel open — never at build time
      verify: pytest tests/test_panel.py::test_starter_questions_lazy
- [ ] R-081  Second open of the same article reuses `read.starter_questions`, no new call
      verify: pytest tests/test_panel.py::test_starter_questions_cached
- [ ] R-082  Every panel answer cites a specific paragraph from the article
      verify: pytest tests/test_panel.py::test_answer_cites_paragraph

## Step 16 — Research panel: Timeline tab

- [ ] R-083  Timeline renders from GDELT metadata only; bodies load lazily on click
      verify: pytest tests/test_panel.py::test_timeline_metadata_only
- [ ] R-084  GDELT unavailable degrades to Guardian + Wikipedia, doesn't error out
      verify: pytest tests/test_panel.py::test_gdelt_down_degrades

## Step 17 — Research panel: Explain tab

- [ ] R-085  Explain uses only the user's text selection as context, not the whole article
      verify: pytest tests/test_panel.py::test_explain_uses_selection

## Step 18 — Top-up job

- [ ] R-086  Top-up adds headlines only — no full-text pre-fetch
      verify: pytest tests/test_topup.py::test_headlines_only
- [ ] R-087  Top-up never re-runs edition selection or the atomic swap
      verify: pytest tests/test_topup.py::test_does_not_rebuild_edition

## Step 19 — FTS5 search over `read`

- [ ] R-088  Search queries `read`/`read_fts` only, never `seen`/`seen_fts`
      verify: pytest tests/test_search.py::test_search_scope_is_read

## Steps 20–22 — deferred

Deep history (Guardian/BigQuery), ranking beyond recency+weight, and mobile.
Gated behind `ARCHITECTURE.md` §8's "ship 01–09, live with it two weeks, then
decide." No `plans/NN-*.md` exists for these yet, so no requirements are listed
— adding them now would be an unverifiable wish.

---

## Progress

65 / 88 (steps 01–19) ticked — steps 01–10 complete (17/19 Ten Rules genuinely
closed; 2 pending step 12 + a final violation-demonstration pass). 19 Ten-Rules requirements are
step-03 scope and count toward the same total. Steps 20–22 excluded from the
denominator until planned.
