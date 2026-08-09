# 00 — Implementation plan

**Status: AWAITING APPROVAL. No application code exists.**

Written 2026-08-08, planning session (Prompt 1). Covers the nine points that
Prompt 1 Step 3 asks for. Per-step plans (`plans/NN-<step>.md`) are written
later, one immediately before each step.

Decisions closed by the user this session are in `logs/SESSIONS.md` S-001…S-004
and are assumed throughout: **3 sections**, **RSS-only ingest of 35 frozen
feeds**, **front page 13 × 3 = 39**, **Haiku 4.5 only**.

---

## 1. Repo layout

Every file and directory I intend to create. Nothing here is created until the
step that needs it — this is the destination, not a scaffold to build now.

```
Project_Aakasavani/
├── CLAUDE.md                     ← exists
├── PROMPT-FOR-CLAUDE-CODE.md     ← exists
├── CONTEXT.md  BLOCKED.md        ← exist
├── REQUIREMENTS.md               ← generated on approval, NOT before
├── .gitignore                    ← exists
├── .env.example                  ← step 01. Committed. Never .env itself
├── pyproject.toml                ← step 01. Deps, pytest config, ruff
│
├── docs/          ARCHITECTURE · EDITION-AND-UI · SOURCES · AUTONOMOUS-LOOP · ROADMAP
├── logs/          ERRORS.md · SESSIONS.md
├── plans/         00-implementation-plan.md (this) · NN-<step>.md
├── .workflow/     STATE.json · BUDGET.json · STOP        [gitignored]
│
├── data/
│   └── feeds.yaml                ← THE registry. 35 frozen feeds, section,
│                                    source_weight, has_full_text. Step 01
│                                    writes has_full_text; the rest is by hand
├── scripts/
│   ├── audit_feeds.py            ← step 01. Fetch each feed once, report
│   └── record_fixtures.py        ← step 02. Regenerates fixtures/ reproducibly
│
├── app/                          ← `python -c "import app"` must succeed
│   ├── __init__.py
│   ├── config.py                 env, caps, constants. No I/O at import time
│   ├── clock.py                  injectable clock. NOTHING calls datetime.now()
│   ├── db.py                     connect, PRAGMAs, migration runner
│   ├── migrations/
│   │   └── 001_initial.sql       §2 of this plan, verbatim
│   ├── net/
│   │   ├── limiter.py            THE shared limiter. One instance, no bypass
│   │   ├── robots.py             robots.txt fetch + 1-day cache
│   │   └── fetcher.py            every outbound HTTP goes through this
│   ├── ingest/
│   │   ├── canonical.py          canonicalise URL → SHA-256
│   │   ├── parser.py             feedparser wrapper, content:encoded
│   │   └── dedupe.py
│   ├── extract/
│   │   └── article.py            3-step fallback: feed → live → Wayback
│   ├── edition/
│   │   ├── select.py             13/section, recency then source_weight
│   │   ├── build.py              the 04:00 job
│   │   └── swap.py               atomic swap
│   ├── ia/queue.py               Internet Archive, async, 6/min
│   ├── research/
│   │   ├── budget.py             BudgetExceeded. Checks BEFORE calling
│   │   ├── client.py             Anthropic, Haiku 4.5 pinned
│   │   └── gdelt.py
│   ├── web/
│   │   ├── main.py               FastAPI app object
│   │   ├── routes.py
│   │   ├── templates/            base · index · article · _row · _panel
│   │   └── static/               app.css · app.js  (vanilla, no build step)
│   └── jobs/
│       ├── topup.py  sweep.py  backup.py
│
├── tests/
│   ├── conftest.py               fixtures only. Network guard. Frozen clock
│   ├── test_rules.py             the Ten Rules. Runs on EVERY verify
│   ├── test_registry.py          01     test_harness.py       02
│   ├── test_schema.py            04     test_fetcher.py       05
│   ├── test_parser.py            06     test_edition.py       07
│   ├── test_feed_view.py         08     test_article_view.py  09
│   ├── test_topics.py            10     test_ia.py            11
│   ├── test_sweep.py             12     test_past_editions.py 13
│   ├── test_budget.py            14     test_panel.py         15-17
│   ├── test_topup.py             18     test_search.py        19
│   └── test_live.py              MANUAL ONLY. Never in the verify chain
│
└── fixtures/
    ├── PROVENANCE.md             where each fixture came from, and when
    ├── feeds/     with_content_encoded · without · malformed · empty
    ├── articles/  normal · paywall_stub · consent_wall · js_shell · cloudflare_403
    ├── gdelt/     artlist · empty
    ├── wayback/   available_hit · available_miss
    └── robots/    permissive · restrictive
```

**`data/feeds.yaml`, not a table seeded by hand.** The frozen list is source
code — it belongs in git where a diff is visible, and `feeds` in SQLite is
populated from it. A frozen list that lives only in a gitignored `.db` cannot be
verified frozen.

---

## 2. SQLite schema

Below is what I will actually run, as `app/migrations/001_initial.sql`.
**Changes from the `ARCHITECTURE.md` §3 draft are marked and justified.** Every
one is either a decision already taken, a table the draft omitted, or a bug.

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE schema_migrations (          -- [NEW] draft had no migration ledger
  version    INTEGER PRIMARY KEY,
  applied_at INTEGER NOT NULL
);

-- ── feeds : source registry, populated from data/feeds.yaml ───────
CREATE TABLE feeds (
  id            INTEGER PRIMARY KEY,
  url           TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  section       TEXT NOT NULL               -- [CHANGED] was `topic`
                CHECK (section IN ('tech','finance','world_india')),
  source_weight INTEGER NOT NULL DEFAULT 3  -- [NEW] 1-5, front-page tie-break
                CHECK (source_weight BETWEEN 1 AND 5),
  has_full_text INTEGER NOT NULL DEFAULT 0, -- step 01 writes this
  enabled       INTEGER NOT NULL DEFAULT 1, -- [NEW] 0 after 10 straight fails
  etag          TEXT,
  last_modified TEXT,
  last_polled   INTEGER,
  fail_count    INTEGER NOT NULL DEFAULT 0
);

-- ── seen : the firehose. TTL'd. Hash retained forever ─────────────
CREATE TABLE seen (
  url_hash      BLOB PRIMARY KEY,           -- SHA-256 of canonical URL
  canonical_url TEXT,
  title         TEXT,
  source        TEXT,
  feed_id       INTEGER REFERENCES feeds(id),  -- [NEW] needed for source_weight
  published_at  INTEGER,
  description   TEXT,                       -- outlet's own words, VERBATIM
  image_url     TEXT,                       -- [NEW] media:content / og:image
  section       TEXT                        -- [CHANGED] was `topic`, 4 values
                CHECK (section IN ('tech','finance','world_india')),
  first_seen    INTEGER NOT NULL,
  expires_at    INTEGER NOT NULL,
  expired       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_seen_pub     ON seen(published_at DESC);
CREATE INDEX idx_seen_expires ON seen(expires_at) WHERE expired = 0;
CREATE INDEX idx_seen_section ON seen(section, published_at DESC);  -- [NEW]

-- ── read : what you opened. Permanent. Never TTL'd ────────────────
CREATE TABLE read (
  url_hash          BLOB PRIMARY KEY,
  canonical_url     TEXT NOT NULL,
  title             TEXT,
  source            TEXT,
  published_at      INTEGER,
  full_text         TEXT,                   -- extractor output, UNALTERED
  content_hash      BLOB,
  fetched_via       TEXT CHECK (fetched_via IN ('feed','live','wayback')),
  read_at           INTEGER NOT NULL,
  dwell_seconds     INTEGER,                -- Rule 9. Unused today
  ia_snapshot       TEXT,
  starter_questions TEXT                    -- [NEW] JSON. EDITION-AND-UI 3.3
);
CREATE INDEX idx_read_at  ON read(read_at DESC);
CREATE INDEX idx_read_pub ON read(published_at DESC);

-- ── editions : the atomic swap ────────────────────────────────────
-- [NEW HERE] defined in EDITION-AND-UI 1.4; 3 omitted it entirely
CREATE TABLE editions (
  id            INTEGER PRIMARY KEY,
  edition_date  TEXT NOT NULL,              -- 'YYYY-MM-DD', IST
  built_at      INTEGER,
  status        TEXT NOT NULL
                CHECK (status IN ('building','live','failed','superseded')),
  article_count INTEGER,
  read_minutes  INTEGER
);
CREATE INDEX idx_editions_live ON editions(status, built_at DESC);

CREATE TABLE edition_items (
  edition_id    INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
  url_hash      BLOB NOT NULL,
  section       TEXT NOT NULL,
  rank_position INTEGER NOT NULL,           -- [RENAMED] `rank` is an SQLite
                                            -- window-function keyword
  PRIMARY KEY (edition_id, url_hash)
);

-- ── topics : saved FTS5 queries, user-editable ────────────────────
-- [NEW HERE] defined in EDITION-AND-UI 2.2; 3 omitted it
CREATE TABLE topics (
  id      INTEGER PRIMARY KEY,
  name    TEXT UNIQUE NOT NULL,
  query   TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1
);

-- ── ia_queue ──────────────────────────────────────────────────────
CREATE TABLE ia_queue (
  url_hash        BLOB PRIMARY KEY,
  url             TEXT NOT NULL,
  queued_at       INTEGER NOT NULL,
  attempts        INTEGER NOT NULL DEFAULT 0,
  last_attempt_at INTEGER,                  -- [NEW] needed for backoff
  done            INTEGER NOT NULL DEFAULT 0
);

-- ── FTS5 ──────────────────────────────────────────────────────────
CREATE VIRTUAL TABLE read_fts USING fts5(
  title, full_text, source, content='read', content_rowid='rowid'
);
-- [NEW] EDITION-AND-UI 2.2 JOINs seen_fts, which 3 never defined.
CREATE VIRTUAL TABLE seen_fts USING fts5(
  title, description, source, content='seen', content_rowid='rowid'
);
```

Plus **six triggers** (`read_ai/ad/au`, `seen_ai/ad/au`) to keep the
external-content FTS tables in sync. **The draft defines `content='read'` and no
triggers — that combination silently yields a permanently empty index.** This is
the single most consequential bug in the draft schema: search would return
nothing, and nothing would error.

### Summary of changes, and why

| # | Change | Reason |
|---|---|---|
| 1 | `topic` → `section`, 3 values, `CHECK` | S-001. `EDITION-AND-UI` §2.1 asked for the rename; it had never reached the schema |
| 2 | `feeds.source_weight` | Front-page tie-break requires it; draft had no column for it |
| 3 | `feeds.enabled` | §5 says disable after 10 failures; `fail_count` alone can't express disabled |
| 4 | `seen.image_url` | Part 6 needs hero/thumbnail URLs; draft had nowhere to put them |
| 5 | `seen.feed_id` FK | Ranking tie-break needs the feed's weight at selection time |
| 6 | `read.starter_questions` | §3.3 says "cached in `read.starter_questions`"; draft omitted it |
| 7 | `editions`, `edition_items`, `topics` | Defined in `EDITION-AND-UI`, absent from §3. §8 step 04 lists them |
| 8 | **`seen_fts` + 6 sync triggers** | §2.2 queries `seen_fts`; §3 defines neither it nor any trigger. **Bug** |
| 9 | `rank` → `rank_position` | `rank` is an SQLite keyword. **Bug** |
| 10 | `schema_migrations` | Step 04 says "schema + migrations"; draft had no ledger |
| 11 | `CHECK` + `NOT NULL` throughout | Cheap invariants. A bad `section` should fail at write, not render blank |
| 12 | `ia_queue.last_attempt_at` | Backoff needs a timestamp |

---

## 3. Build order

**`ARCHITECTURE.md` §8, unchanged and unduplicated.** I am not restating the
table. `.workflow/STATE.json` carries the machine-readable dependency graph.

Two notes on sequencing, neither a change:

- **01 → 02 → 03 is fixed.** They are the oracle. 01 is not code.
- **Steps 01–09 are the product** (`ARCHITECTURE.md` §8). See §8 R-7 below for a
  contradiction about whether that number is 5 or 9.

---

## 4. Named test for every Phase-1 feature

A feature with no named test does not go in the plan. Rule tests (step 03) are
in §6 and not repeated here.

| Step | Feature | Test |
|---|---|---|
| 01 | Registry is the 35 frozen feeds | `test_registry.py::test_registry_matches_frozen_list` |
| 01 | Every feed has section + weight | `::test_every_feed_has_section_and_weight` |
| 01 | `has_full_text` recorded for all | `::test_has_full_text_recorded_for_every_feed` |
| 01 | No Google News in frozen list | `::test_no_google_news_redirect_sources` |
| 02 | Network is physically blocked | `test_harness.py::test_network_access_raises` |
| 02 | Clock is frozen and injected | `::test_clock_is_frozen` |
| 02 | Temp DB, never the real one | `::test_db_is_temporary` |
| 02 | Every declared fixture exists | `::test_all_fixtures_present` |
| 04 | Migrations apply and are idempotent | `test_schema.py::test_migrations_idempotent` |
| 04 | PRAGMAs set (WAL, FK, busy) | `::test_pragmas_applied` |
| 04 | FTS triggers keep index in sync | `::test_fts_stays_in_sync_on_insert_update_delete` |
| 04 | FK on `edition_items` enforced | `::test_edition_items_fk_enforced` |
| 04 | Bad `section` rejected | `::test_section_check_constraint` |
| 05 | 1 req/sec/domain | `test_fetcher.py::test_one_request_per_second_per_domain` |
| 05 | Limiter cannot be bypassed | `::test_all_fetches_go_through_limiter` |
| 05 | `robots.txt` disallow blocks fetch | `::test_robots_disallow_blocks_fetch` |
| 05 | `robots.txt` cached 1 day/domain | `::test_robots_cached_per_day` |
| 05 | <500 chars = failure | `::test_short_extraction_is_failure` |
| 05 | Fallback order feed→live→wayback | `::test_fallback_chain_order` |
| 05 | All three fail → headline + link | `::test_total_failure_returns_headline_only` |
| 05 | Wayback 429 backs off globally | `::test_wayback_429_global_backoff` |
| 06 | `content:encoded` extracted | `test_parser.py::test_content_encoded` |
| 06 | Absent `content:encoded` → `None` | `::test_missing_content_encoded` |
| 06 | Malformed XML does not crash | `::test_malformed_xml_survives` |
| 06 | Empty feed → zero items | `::test_empty_feed` |
| 06 | Canonicalise strips `utm_*`/fragment | `::test_canonicalise_strips_tracking` |
| 06 | Same URL + different `utm` = same hash | `::test_tracking_params_do_not_change_hash` |
| 06 | Duplicate hash skipped | `::test_duplicate_is_skipped` |
| 06 | Description fallback chain | `::test_description_fallback_order` |
| 07 | 13 per section selected | `test_edition.py::test_selects_13_per_section` |
| 07 | Recency then source weight | `::test_ranking_recency_then_weight` |
| 07 | Whole front page pre-fetched | `::test_every_front_page_item_prefetched` |
| 07 | Swap only on success | `::test_swap_only_on_success` |
| 08 | Front page renders the edition | `test_feed_view.py::test_front_page_renders_edition` |
| 08 | Section chips filter | `::test_section_chip_filters` |
| 08 | Hero on section lead only | `::test_hero_on_lead_only` |
| 08 | No image → text-only row | `::test_missing_image_renders_text_only` |
| 08 | "Show everything" lists remainder | `::test_show_everything_lists_remainder` |
| 09 | Served from pre-fetched text | `test_article_view.py::test_served_from_prefetch` |
| 09 | `dwell_seconds` written | `::test_dwell_seconds_written` |
| 09 | Opening creates a `read` row | `::test_read_row_created` |
| 10 | Topic query matches | `test_topics.py::test_topic_query_matches` |
| 10 | New topic matches history | `::test_new_topic_is_retroactive` |
| 10 | Topics editable at runtime | `::test_topic_editable` |
| 11 | Front page enqueued to IA | `test_ia.py::test_front_page_enqueued` |
| 11 | ≤6/min | `::test_rate_six_per_minute` |
| 11 | Retry ≤3 then abandon | `::test_retries_thrice_then_abandons` |
| 11 | Never blocks a request | `::test_never_blocks_request` |
| 12 | Sweep strips text, keeps hash | `test_sweep.py::test_sweep_strips_keeps_hash` |
| 12 | Sweep idempotent | `::test_sweep_idempotent` |
| 12 | Backup readable | `::test_backup_is_readable` |
| 13 | `/edition/YYYY-MM-DD` | `test_past_editions.py::test_edition_by_date` |
| 13 | Unknown date → 404 | `::test_unknown_date_404` |
| 13 | `/` serves latest live | `::test_root_serves_latest_live` |
| 14 | Raises **before** calling | `test_budget.py::test_raises_before_calling` |
| 14 | Single-call cap | `::test_single_call_cap` |
| 14 | Daily + monthly caps | `::test_daily_cap`, `::test_monthly_cap` |
| 14 | Breach never breaks reading | `::test_breach_does_not_break_reading` |
| 15 | Starter questions lazy | `test_panel.py::test_starter_questions_lazy` |
| 15 | Starter questions cached | `::test_starter_questions_cached` |
| 15 | Answer cites a paragraph | `::test_answer_cites_paragraph` |
| 16 | Timeline from metadata only | `::test_timeline_metadata_only` |
| 16 | GDELT down degrades gracefully | `::test_gdelt_down_degrades` |
| 17 | Explain uses selection only | `::test_explain_uses_selection` |
| 18 | Top-up adds headlines only | `test_topup.py::test_headlines_only` |
| 18 | Top-up does not rebuild edition | `::test_does_not_rebuild_edition` |
| 19 | Search covers `read` only | `test_search.py::test_search_scope_is_read` |

---

## 5. Recording fixtures

`scripts/record_fixtures.py`, run manually, never by the loop. It is the only
script besides `test_live.py` permitted to touch the network.

**The pathological fixtures are the point, and most cannot be captured on
demand** — you cannot ask a site to 403 you, and a paywall stub varies by
geography and cookie state. So provenance splits three ways, and each fixture
records which it is in `fixtures/PROVENANCE.md`:

| Kind | How | Fixtures |
|---|---|---|
| **Captured** | Real response, saved verbatim, secrets scrubbed | `feeds/with_*`, `feeds/without_*`, `articles/normal`, `robots/*`, `gdelt/*`, `wayback/*` |
| **Derived** | Real response, minimally mutated to create the pathology | `feeds/malformed.xml` (truncate mid-tag), `feeds/empty.xml` (strip items) |
| **Hand-authored** | Written from the documented shape of the real thing | `articles/paywall_stub`, `consent_wall`, `js_shell`, `cloudflare_403` |

Rules that make a fixture trustworthy:

- **`PROVENANCE.md` records source URL, capture date, kind, and what pathology it
  encodes.** A fixture whose origin nobody remembers is a fixture nobody dares
  update.
- **Trim, never edit for convenience.** Truncating a 400-item feed to 5 is fine.
  Fixing malformed markup so the parser passes is falsifying the oracle.
- **Byte-exact on disk**, opened as bytes. Encoding bugs (cp1252 vs utf-8 — see
  R-3) only reproduce if the bytes are preserved.
- **Re-record when a feed changes format.** A stale fixture is a lie that passes.
- **Scrub** cookies, `Set-Cookie`, auth headers, API keys before committing.

Sizes are held down deliberately: 5 items per feed fixture, one article body per
HTML fixture. `fixtures/` is committed; only `fixtures/.cache/` is ignored.

---

## 6. The Ten Rules as tests

`tests/test_rules.py`, per `ARCHITECTURE.md` §12.1. Runs on **every** verify.

The important design point: **four of these must be static-analysis tests, not
behavioural ones.** A behavioural test proves the LLM was not called *on the path
the test exercised*. Only walking the import graph proves it cannot be called at
all. Rules 1, 4, 6 and 10 are enforced by parsing the AST / import graph of
`app.web` and `app.edition`, which is what makes them hard to defeat by accident.

| Rule | Test(s) | Mechanism |
|---|---|---|
| 1 · No AI text in reading path | `test_no_llm_import_in_render_path` | **Static.** Walk imports transitively from `app.web.routes` render handlers and `app.edition`; assert `anthropic` unreachable |
| | `test_feed_description_is_verbatim` | Stored `seen.description` equals feed `<description>` byte-for-byte (see D-1 on rendering) |
| 2 · No synthesis | `test_six_outlets_six_entries` | Six fixture feeds, one story → six `seen` rows, six distinct hashes |
| 3 · Whole and unaltered | `test_stored_text_equals_extractor_output` | `read.full_text` is identical to the extractor's return value — no strip, no truncate, no normalise |
| 4 · Pull, not push | `test_build_makes_zero_llm_calls` | Run the whole 04:00 build against fixtures with the Anthropic client patched to raise on any call |
| | `test_no_llm_import_in_build_path` | **Static**, as Rule 1 |
| 5 · TTL firehose, keep reads | `test_sweep_strips_text_keeps_hash` | After sweep: `title`/`description`/`source` NULL, `expired=1`, `url_hash` present |
| | `test_read_rows_never_expire` | Sweep with clock at +10 years; `read` untouched |
| 6 · Pre-fetch, never at click | `test_no_network_on_request_path` | **Static + behavioural.** Reading handlers unreachable from `app.net.fetcher`; plus request under the network guard (see D-2 on panel scope) |
| 7 · Never an empty page | `test_failed_build_keeps_previous_edition` | Build raises mid-way; previous edition still served |
| | `test_swap_is_atomic` | Failure inside the swap transaction leaves zero partial `edition_items` |
| 8 · Never evade bot detection | `test_rate_limiter_is_shared_and_enforced` | Two callers, same domain → ≥1s apart. Single shared instance |
| | `test_user_agent_is_honest` | UA matches the `ARCHITECTURE.md` §6 string, contains contact address, contains no browser impersonation |
| | `test_robots_txt_respected` | `restrictive.txt` fixture → fetch refused |
| | `test_no_evasion_dependencies` | **Static.** No `selenium`, `undetected_chromedriver`, `playwright-stealth`, `cloudscraper`, `fake_useragent` |
| 9 · Log read_at / dwell | `test_read_schema_has_dwell_columns` | Columns exist and are writable |
| | `test_article_view_writes_dwell` | Opening then leaving writes a non-null `dwell_seconds` |
| 10 · SQLite, single process | `test_no_forbidden_dependencies` | **Static.** No `psycopg2`, `redis`, `celery`, `pinecone`, `chromadb`, `sqlalchemy`, `kombu`, `pymongo` |

**Step 03 acceptance is not "these pass".** It is that each has been *observed
catching a real violation*: break the guarded thing, watch it go red, restore.
Prompt 2 requires me to demonstrate this to you. A rule test that has never
caught anything is decoration.

---

## 7. What I need from you

Detail in `BLOCKED.md`. Summary, in the order it bites:

| # | Need | Blocks | When |
|---|---|---|---|
| **B-001** | **Python version decision** — spec pins 3.12; only 3.14.3 and 3.13 installed. Recommend installing **3.12** to match the Ubuntu 24.04 target | **01, and so everything** | **Now** |
| B-002a | `IA_S3_ACCESS_KEY` / `IA_S3_SECRET_KEY` — free, `archive.org/account/s3.php` | 11 | Before step 11 |
| B-002b | `ANTHROPIC_API_KEY` — the only paid item | 14–17 | Before step 14 |
| B-002c | `GUARDIAN_API_KEY` — free, 5k/day | 20 | Before step 20 |
| B-002d | `AAKASAVANI_PASSWORD` — choose one | deploy | Before deploy |

**Only B-001 blocks starting.** Steps 01–09 — the entire product — need no
credentials at all.

Also needed, but from you as reviewer rather than as inputs:

- **Approval of this plan**, which unlocks `REQUIREMENTS.md`.
- **Approval of the schema in §2**, particularly the twelve changes.
- **Rulings on D-1 … D-4 in §9.** D-1 and D-2 change what a rule test asserts, so
  they must be settled before step 03, not discovered during it.
- Switch to **Sonnet 5** when we move from planning to building.

---

## 8. Risks and ambiguities found in the docs

| # | Risk | Severity | Handling |
|---|---|---|---|
| **R-1** | ~~Python 3.12 not installed; `lxml` wheels may be missing on 3.14~~ **RETIRED — tested, not a risk.** lxml 6.1.1 / trafilatura 2.2.0 / feedparser 6.0.14 / fastapi 0.141.1 all install as binary wheels on 3.14.3 and run correctly | ~~High~~ **None** | `BLOCKED.md` B-001. Residual: dev 3.14 vs prod 3.12 drift, a deploy-time decision only |
| **R-2** | **Dev is Windows, prod is Ubuntu.** Paths, `cron` absent, `sqlite3` CLI absent, file locking differs. `.backup` via CLI won't exist locally | Medium | Use `pathlib` everywhere; backup via `sqlite3` **module** `.backup()` API, not the CLI; keep cron out of app code (step 12 ships a callable, cron just calls it) |
| **R-3** | **Console is cp1252.** Already hit this session — printing `│` crashed Python. Will recur in any script that prints feed titles | Medium | `PYTHONIOENCODING=utf-8`; always `encoding='utf-8'` on `open()`; never rely on locale default |
| **R-4** | **`~120 feeds` storage projection.** §3 projects 292k `seen` rows/yr from ~120 feeds. With 35 the real figure is ~300–500/day | Low | Projection is now conservative. No action; noted so nobody "fixes" the arithmetic later |
| **R-5** | **`read_minutes` undefined.** `editions.read_minutes` has no stated formula | Low | Define as `ceil(total_words / 220)`. Will state it in `plans/07-*.md` |
| **R-6** | **Trafilatura config is unpinned but Rule 3 depends on it.** `extract()` drops images by default, and output format changes the bytes stored. `test_stored_text_equals_extractor_output` is meaningless without a frozen config | **High** | Pin one call signature in `app/extract/article.py` as a module constant, assert it in a test. Needs `include_images=True` for Part 6 |
| **R-7** | **"Ship steps 1–5" vs "steps 01–09 are the product."** `ROADMAP.md` and `CLAUDE.md` say 5; `ARCHITECTURE.md` §8 says 01–09. At step 05 there is no edition and no UI, so 5 cannot be right | Medium | ARCHITECTURE wins → **09**. Will patch `ROADMAP.md` + `CLAUDE.md` on approval, logging S-005 |
| **R-8** | **Broken cross-references.** `CLAUDE.md` cites `ARCHITECTURE.md` §11 for doc retirement — §11 does not exist, it is §13, and §13 is printed *before* §12. `EDITION-AND-UI.md` says dwell is logged "from step 4" (it is 09). `ARCHITECTURE.md` §9 calls the panel "step 9–11" (it is 15–17) | Medium | Patch all four on approval under S-005. Stale pointers are how an agent builds confidently from the wrong section |
| **R-9** | **`robots.txt` disallow + Wayback.** If robots forbids the article, may we serve the Wayback copy? Reading a public archive is not crawling the publisher — but it does obtain content they asked us not to take | Medium | **Recommend the strict reading:** robots disallow → no live fetch **and** no Wayback; headline + link only. Cheap, unambiguous, matches Rule 8's spirit. Flagged as D-3 |
| **R-10** | **NYT and several World feeds are hard-paywalled.** Expect `has_full_text=0` plus live-fetch failure plus a paywalled Wayback copy — the honest floor for a chunk of the World section | Medium | Not a defect. Step 01 will quantify it. If a section is mostly floor, that is a real finding for you, not something to engineer around |
| **R-11** | **PIB feed is an `.aspx` query string** and historically returns malformed XML | Low | Frozen list — a dead feed is a BLOCKED item, never a substitution. `malformed.xml` fixture covers the parser side |
| **R-12** | **Google News redirect resolution is dead code in Phase 1.** §2.2 requires it, but no frozen feed is Google News | Low | Do not build it. Add `test_no_google_news_redirect_sources` so the day one is added, the missing resolver fails loudly |
| **R-13** | **Local dev has no Caddy, so no auth.** Rule "never serve stored text to anyone else" is enforced by infrastructure absent in dev | Low | Bind dev server to `127.0.0.1` only. Deployment checklist item, not a code test |
| **R-14** | **Timezone.** Everything is IST-scheduled but stored as unix seconds | Medium | Store UTC unix seconds always; convert at the edges only; `app/clock.py` is the single source of "now" and is frozen in tests |
| **R-15** | **`test_swap_is_atomic` says "killed mid-build."** A real SIGKILL test is not practical in pytest and would be flaky | Low | Assert transactional atomicity (raise inside the transaction → no partial rows). True kill-testing goes in `test_live.py` as a manual check |

---

## 9. Where I disagree with the spec

Four. The first two change what a rule test asserts, so they need rulings before
step 03.

### D-1 · Rule 1 "byte-for-byte" cannot survive rendering, only storage

`ARCHITECTURE.md` §12.1 wants the *rendered* blurb to equal the source
`<description>` byte-for-byte. RSS descriptions routinely contain HTML —
`<p>`, `<a>`, `&nbsp;`, occasionally a tracking pixel. Rendering those bytes
literally leaves three options and all three break something: escape it (reader
sees `&lt;p&gt;`), mark it `|safe` (injects publisher HTML and a tracking pixel
into my page), or strip tags (no longer byte-for-byte).

**Measured 2026-08-08 — it is worse than that. "Byte-for-byte" is already
impossible at the parse layer**, before rendering is even reached:

```
RSS on the wire :  Outlet blurb &amp; entity &lt;b&gt;markup&lt;/b&gt;
feedparser gives:  Outlet blurb & entity <b>markup</b>
```

feedparser decodes HTML entities itself. The bytes it hands you are not the
bytes in the feed, and what comes back contains live markup. No implementation
can satisfy the rule as written — not by choice of renderer, not by choice of
parser.

**I propose the test asserts storage, not rendering:** `seen.description` is
byte-for-byte identical to the feed. Rendering applies a tag allowlist, and a
second test asserts sanitisation only ever *removes markup* and never alters,
reorders, or rewords the text content. That keeps the rule's actual intent — no
AI-written text, no rewording — while remaining implementable.

**Why it matters:** as written, the test is unimplementable, and an autonomous
agent that meets it literally will do so by marking publisher HTML `|safe`.

### D-2 · Rule 6's "no network on the request path" must exclude the panel

`test_no_network_on_request_path` asserts request handlers make no outbound HTTP.
But the research panel is a request handler that calls Anthropic and GDELT by
design — that is Rule 4's "pull". Taken literally, Rule 6 forbids step 15
entirely.

**I propose the test scopes to the reading path** — `/`, `/edition/*`,
`/article/*` — and explicitly asserts `/research/*` is the *only* handler
permitted outbound access. Better than an exemption: it names the boundary, so
network access silently appearing in the article view fails immediately.

### D-3 · `robots.txt` disallow should also block the Wayback fallback

See R-9. Not stated either way in the docs. I recommend the strict reading and
want it ruled on rather than assumed, because it is exactly the kind of
"technically permitted" gap an unattended loop would resolve in the permissive
direction at 3am.

### D-4 · `ARCHITECTURE.md` §2.1's "every 15 minutes" ingest worker is stale

§2.1 describes an ingest worker running every 15 minutes. Nothing else supports
it: the cron table in §10 of the same document lists only build, top-up, sweep
and backup, and `EDITION-AND-UI.md`'s whole thesis is that the river was replaced
by an edition. The 15-minute worker is a survivor of the pre-edition design.

**I propose deleting it.** Polling happens inside the 04:00 build and the 30-min
top-ups. Keeping it would triple fetch volume against the frozen feeds for no
user-visible benefit and undermine Rule 8's politeness posture.

---

## 10. What happens on approval

1. Generate `REQUIREMENTS.md` — every line with a `verify:` command, IDs `R-NNN`.
2. Patch the R-7/R-8 stale references, log as S-005.
3. Apply rulings on D-1…D-4, log as S-006, patch the contradicted docs.
4. Write `plans/01-feed-audit.md`.
5. Run step 01 supervised, then 02, then 03. **Stop after 03.**

Autonomous mode stays forbidden until you have watched the rule tests catch real
violations — `AUTONOMOUS-LOOP.md` precondition 8.
