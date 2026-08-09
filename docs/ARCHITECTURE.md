# Project Aakasavani — System Architecture

**Master document — this is the build spec.**

Companion documents in `docs/`:

| File | Role |
|---|---|
| `EDITION-AND-UI.md` | **SPEC** — overnight build, categories, images, research panel |
| `SOURCES.md` | **REFERENCE** — feeds, API endpoints, content rights |
| `AUTONOMOUS-LOOP.md` | **PROCESS** — the unattended build protocol |
| `ROADMAP.md` | **GUARD RAIL** — Phase 1 / 2 / 3 boundaries |

Where any document disagrees with this one, **this one wins.**

Personal newsletter — Tech/AI/dev, Finance & markets, World & India news.
Single user. Web first, mobile later.

---

## 0. Design principles

Every one of these was arrived at by rejecting a more complicated alternative.

| # | Principle | Rejected alternative |
|---|---|---|
| 1 | **No AI-generated text in the reading path** | Per-article LLM summaries |
| 2 | **No cross-article synthesis** | "Unified true article", claim extraction, truth adjudication |
| 3 | **Articles shown whole and unaltered** | Rewriting, condensing, reframing |
| 4 | **History fetched live, not warehoused** | Full permanent archive of all ingested articles |
| 5 | **Keep only what you actually read** | Store everything / store nothing |
| 6 | **TTL the firehose, keep the reads** | Uniform retention policy |
| 7 | **Push durability to the Internet Archive** | Rely on publishers keeping URLs alive |
| 8 | **Single file database** | Postgres, vector DB, message broker |

Consequence: no LLM on the reading path at all, ~$5–10/month total, and a build
small enough to finish in a few weekends.

---

## 1. Full system diagram

```
════════════════ DAILY LOOP ═══════════════╗════════════ ON DEMAND ═════════════

  ┌──────────────────────────────────┐     ║
  │ SOURCES                          │     ║
  │  35 RSS feeds — SOURCES.md §1    │     ║
  │  FROZEN · RSS only in Phase 1    │     ║
  │  GDELT: Flow C only, on demand   │     ║
  └────────────────┬─────────────────┘     ║
                   │                       ║
                   ▼                       ║
  ┌──────────────────────────────────┐     ║
  │ INGEST WORKER   every 15 min     │     ║
  │  conditional GET (etag/modified) │     ║
  │  parse feed → normalise fields   │     ║
  └────────────────┬─────────────────┘     ║
                   │                       ║
                   ▼                       ║
  ┌──────────────────────────────────┐     ║
  │ DEDUPE                           │     ║
  │  canonicalise URL (strip utm_*)  │     ║
  │  SHA-256 → lookup in `seen`      │     ║
  └────────────────┬─────────────────┘     ║
                   │ new only              ║
                   ▼                       ║
  ╔══════════════════════════════════╗     ║
  ║ SQLite · TABLE seen              ║     ║
  ║   headline, link, outlet blurb   ║     ║
  ║   expires_at = now + 30 days     ║     ║
  ║   sweep: strip text, KEEP hash   ║     ║
  ║   ≈ 9 MB / year after sweep      ║     ║
  ╚════════════════╤═════════════════╝     ║
                   │                       ║
                   ▼                       ║
  ┌──────────────────────────────────┐     ║
  │ FEED VIEW        (web page)      │     ║
  │  headline + outlet's own text    │     ║
  │  recency ordered                 │     ║
  └────────────────┬─────────────────┘     ║
                   │ you click             ║
                   ▼                       ║
  ┌──────────────────────────────────┐     ║   ┌─────────────────────────────┐
  │ GET FULL TEXT                    │─ ─ ─╫─ ▶│ LIVE HISTORY LOOKUP         │
  │  1. feed content:encoded  ← free │"research│  GDELT DOC 2.0              │
  │  2. live fetch → Trafilatura     │  this"  │    last 3 months, free, ~1s │
  │  3. Wayback CDX (dead/403/stub)  │     ║   │  GDELT BigQuery             │
  └────────────────┬─────────────────┘     ║   │    Feb 2015 →, partitioned  │
                   │                       ║   │  Guardian Open Platform     │
        ┌──────────┴───────────┐           ║   │    1999 →, FULL TEXT        │
        │                      │           ║   │  Wayback CDX                │
        ▼                      ▼           ║   │    recovers dead URLs       │
  ╔═══════════════════╗  ┌──────────────┐  ║   └──────────────┬──────────────┘
  ║ SQLite · read     ║  │ QUEUE        │  ║                  │
  ║  full_text        ║  │  rate 6/min  │  ║                  ▼
  ║  content_hash     ║  │  async       │  ║   ┌─────────────────────────────┐
  ║  read_at, dwell   ║  └──────┬───────┘  ║   │ CHRONOLOGY VIEW             │
  ║  ia_snapshot      ║         │          ║   │  timeline in ~1 s           │
  ║  PERMANENT        ║         ▼          ║   │  from metadata only         │
  ║  ≈165 MB / year   ║  ┌──────────────┐  ║   │  bodies load lazily         │
  ╚═════════╤═════════╝  │ INTERNET     │  ║   └──────────────┬──────────────┘
            │            │ ARCHIVE      │  ║                  │
            ▼            │ POST /save   │  ║                  ▼
  ┌───────────────────┐  │ public copy  │  ║   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
  │ FTS5 SEARCH       │  └──────────────┘  ║     nothing here is stored
  │ over your reads   │                    ║   │ unless you open and read it │
  └───────────────────┘                    ║    ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

**Read the diagram as two loops.** The left runs continuously and is the product.
The right runs only when you explicitly ask for history, touches no storage, and
could be deleted entirely without breaking anything.

---

## 2. Components

### 2.1 Ingest worker

Runs as part of the 04:00 edition build and the :30 top-up jobs — see
`EDITION-AND-UI.md` Part 1. **Not a standalone poller.** An earlier draft of
this section described one running independently every 15 minutes; that was a
leftover of a pre-edition "continuous river" design this project explicitly
rejected (§0 principle 4, and `EDITION-AND-UI.md` §0's river-vs-edition table).
It also wasn't in the cron table in §10, and a 15-minute cadence would triple
fetch volume against the 35 frozen feeds for no user-visible benefit, straining
Rule 8's politeness posture. Deleted 2026-08-09 — `logs/SESSIONS.md` D-4/S-006.

- **Conditional GET** — send `If-None-Match` / `If-Modified-Since` per feed.
  Most polls return `304 Not Modified` and cost nothing. Cuts bandwidth ~95%.
- **Parse** — `feedparser` (Python) or `rss-parser` (Node).
- **Normalise** to a common record regardless of source:
  `{url, title, source, published_at, description, body?}`
- **`body`** is populated only when the feed ships `<content:encoded>`.
  **This is the single highest-value thing to check per feed** — those sources
  never need fetching, never hit a 403, and never need a fallback.
- Per-domain politeness: ≤1 req/sec, honest descriptive User-Agent with contact
  address, respect `robots.txt`.

### 2.2 Dedupe

1. **Canonicalise** — lowercase host, strip `utm_*`/`fbclid`/fragments, resolve
   Google News redirect URLs to the publisher URL, drop trailing slash.
2. **Hash** — SHA-256 of the canonical URL.
3. **Lookup** in `seen`. Present → discard. Absent → insert.

Note this is *URL* dedup, not *story* dedup. The same event from six outlets
yields six rows, deliberately — you see how different outlets led it, which was
the point of dropping synthesis.

### 2.3 Feed view

Headline plus the outlet's own description, sourced in this order:

```
RSS <description> / <summary>
  → og:description
    → twitter:description
      → first ~200 chars of body (if feed shipped one)
        → headline alone
```

Recency ordered. **Ranking is deliberately deferred to last** — live with
chronological for a few weeks before deciding what smarter would even mean.

### 2.4 Get full text

Three-step fallback, cheapest first:

| Step | Method | Cost | Notes |
|---|---|---|---|
| 1 | Feed `content:encoded` | **free, instant** | No network call. Audit feeds for this |
| 2 | Live fetch → Trafilatura | ~1–2 s | F1 ≈ 0.945, best open-source extractor |
| 3 | Wayback CDX → nearest snapshot | ~3–10 s | For 404 / 403 / paywall stub |

**Failure detection is not just HTTP status.** Treat as failed and fall through
when extraction yields **< 500 characters** — this catches paywall stubs, consent
walls and bot-challenge pages that all return `200 OK`.

If all three fail: show headline + description + "open at source" link. Honest
floor, not an error.

### 2.5 Storage

SQLite, single file, on the VPS disk. See §3.

### 2.6 Internet Archive queue

On every read, enqueue the URL. Background worker drains it at ≤6/min and
`POST`s to `web.archive.org/save`. Writes the snapshot URL back to `read`.

Fully asynchronous — a capture takes 10–60 s and must never block the reader.
An in-process queue with a rate limiter is sufficient; no broker required.

### 2.7 Live history lookup

Triggered explicitly from an article. Query order:

1. **Wikipedia** — check for an existing curated timeline article first. Free,
   instant, often better than anything auto-assembled
2. **GDELT DOC 2.0** — `sort=dateasc`, last 3 months, no key, ~1 s
3. **GDELT BigQuery** — Feb 2015 →, **must filter on `_PARTITIONTIME`**
4. **Guardian Open Platform** — 1999 →, full text, `from-date`/`to-date`
5. **Wayback CDX** — recover dead URLs from any of the above

**Render metadata immediately, load bodies lazily.** The timeline appears in ~1
second; article text loads only when you click a specific entry. This is what
makes on-demand history feel fast despite fetching nothing in advance.

---

## 3. Data model

```sql
-- ─────────────────────────────────────────────────────────────
-- seen : the firehose. TTL'd. Hash retained forever.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE seen (
  url_hash      BLOB PRIMARY KEY,      -- SHA-256 of canonical URL
  canonical_url TEXT,
  title         TEXT,
  source        TEXT,
  published_at  INTEGER,               -- unix seconds
  description   TEXT,                  -- outlet's own words
  section       TEXT,                  -- tech | finance | world_india
  first_seen    INTEGER NOT NULL,
  expires_at    INTEGER NOT NULL,
  expired       INTEGER DEFAULT 0      -- 1 = text stripped, hash kept
);
CREATE INDEX idx_seen_pub     ON seen(published_at DESC);
CREATE INDEX idx_seen_expires ON seen(expires_at) WHERE expired = 0;

-- ─────────────────────────────────────────────────────────────
-- read : what you actually opened. Permanent. Never TTL'd.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE read (
  url_hash      BLOB PRIMARY KEY,
  canonical_url TEXT NOT NULL,
  title         TEXT,
  source        TEXT,
  published_at  INTEGER,
  full_text     TEXT,                  -- extracted body
  content_hash  BLOB,                  -- detects later stealth edits
  fetched_via   TEXT,                  -- feed | live | wayback
  read_at       INTEGER NOT NULL,
  dwell_seconds INTEGER,               -- unused today, irreplaceable later
  ia_snapshot   TEXT                   -- Wayback URL, filled async
);
CREATE INDEX idx_read_at  ON read(read_at DESC);
CREATE INDEX idx_read_pub ON read(published_at DESC);

-- ─────────────────────────────────────────────────────────────
-- Full-text search over your own reading history
-- ─────────────────────────────────────────────────────────────
CREATE VIRTUAL TABLE read_fts USING fts5(
  title, full_text, source,
  content='read', content_rowid='rowid'
);

-- ─────────────────────────────────────────────────────────────
-- feeds : source registry and poll state
-- ─────────────────────────────────────────────────────────────
CREATE TABLE feeds (
  id            INTEGER PRIMARY KEY,
  url           TEXT UNIQUE NOT NULL,
  name          TEXT,
  section       TEXT,                  -- tech | finance | world_india
  source_weight INTEGER DEFAULT 3,     -- 1-5, hand-written, front-page tie-break
  has_full_text INTEGER DEFAULT 0,     -- ships content:encoded?
  etag          TEXT,
  last_modified TEXT,
  last_polled   INTEGER,
  fail_count    INTEGER DEFAULT 0
);

-- ─────────────────────────────────────────────────────────────
-- ia_queue : pending Internet Archive snapshots
-- ─────────────────────────────────────────────────────────────
CREATE TABLE ia_queue (
  url_hash   BLOB PRIMARY KEY,
  url        TEXT NOT NULL,
  queued_at  INTEGER NOT NULL,
  attempts   INTEGER DEFAULT 0,
  done       INTEGER DEFAULT 0
);
```

### The daily sweep

```sql
UPDATE seen
   SET title = NULL, description = NULL, source = NULL, expired = 1
 WHERE expires_at < unixepoch() AND expired = 0;
```

Text is stripped; the hash survives. You permanently remember having seen an
article for ~32 bytes.

### Storage projection

| Table | Rows/yr | Bytes/row | Total/yr |
|---|---|---|---|
| `seen` (after sweep) | ~292,000 | ~32 | **~9 MB** |
| `seen` (live 30-day window) | ~24,000 | ~400 | ~10 MB steady |
| `read` | ~7,000 | ~15,000 | **~105 MB** |
| `read_fts` index | — | — | ~50 MB |
| **Total after year 1** | | | **~175 MB** |

---

## 4. The three data flows

### Flow A — Ingest (continuous, unattended)

```
cron 15min → for each feed:
    conditional GET
    304? → done
    200? → parse → for each item:
             canonicalise → hash
             hash in seen? → skip
             else → INSERT seen (expires_at = now + 30d)
```

### Flow B — Read (interactive, ~1–2 s)

```
click headline
  → row already in read?  → serve stored copy instantly, done
  → else:
      body in feed?       → use it
      else live fetch     → Trafilatura → extraction ≥500 chars?
      else Wayback CDX    → nearest snapshot → extract
      else                → headline + link only

  → INSERT read (full_text, content_hash, read_at, fetched_via)
  → INSERT ia_queue                          ← async, fire and forget
  → render
```

### Flow C — Research (explicit, ~1 s to first paint)

```
click "research this"
  → Wikipedia timeline exists?  → show it
  → GDELT DOC (≤3 months)  ─┐
  → BigQuery (older)        ─┼→ merge, sort by date ascending
  → Guardian API            ─┘
  → RENDER TIMELINE          ← metadata only, ~1 second

  → user clicks one entry → Flow B for that URL
```

Nothing from Flow C is persisted unless the user opens an entry, at which point
it becomes an ordinary read.

---

## 5. Failure handling

| Failure | Response |
|---|---|
| Feed 404 / timeout | Increment `fail_count`; disable after 10 consecutive; log |
| Article 403 (bot block) | Fall to Wayback. **Expect this to worsen after 15 Sep 2026** |
| `robots.txt` disallows the article | **No live fetch, no Wayback fallback either** — headline + description + link only. Reading a public archive of content the publisher's own `robots.txt` asked us not to take defeats the point of honouring it. `logs/SESSIONS.md` D-3/S-006 |
| Extraction < 500 chars | Treat as failure, fall through — catches paywalls and consent walls |
| Wayback 429 | Exponential backoff across *all* workers, not per-request |
| IA save fails | Retry ≤3×, then abandon. Never surfaced to the user |
| GDELT down | Chronology degrades to Guardian + Wikipedia only |
| BigQuery quota exhausted | Cap history at 3 months for the rest of the month; warn in UI |
| SQLite locked | Enable WAL mode; single writer means this should not occur |

**Do not attempt to defeat bot detection** — no proxy rotation, no fingerprint
spoofing, no headless evasion. That converts a defensible personal-reading
posture into an adversarial one.

---

## 6. Deployment — DECIDED

```
VPS · Hetzner CX22 (or equivalent), ~€4/mo, Ubuntu 24.04
├── Caddy                 — TLS, HTTP basic auth
├── app process           — FastAPI: web + scheduler + IA queue worker
├── aakasavani.db         — SQLite, WAL mode
└── cron                  — build 04:00, top-up :30, sweep 03:00, backup 02:30
```

**Auth: HTTP basic auth at Caddy, single user, password from env.** Not a login
page, not sessions, not accounts. One password in `AAKASAVANI_PASSWORD`. This is
the minimum that keeps `read` full text non-public, which is the only thing auth
must achieve here (`SOURCES.md` §6 — the line that matters is *serving*).

**Past editions: browsable by date.** `GET /` serves the latest `live` edition;
`GET /edition/YYYY-MM-DD` serves any prior one. The `editions` table already
supports it and it costs nothing.

**Backup on day one.** `read` is the only irreplaceable data; everything else can
be re-fetched from the internet.

### Spend ceiling — enforced in code, not in prose

Every Anthropic call goes through one wrapper that checks the cap **before**
calling and raises `BudgetExceeded` if the request would breach it. A ledger
appended to after the fact does not cap anything.

```python
# config
MONTHLY_USD_CAP   = 25.00
DAILY_USD_CAP     = 2.00
SINGLE_CALL_CAP   = 0.10     # refuse any single request above this
```

Cap breach → panel returns "budget reached for today", app keeps working. The
reading path has no LLM, so a budget breach must never break reading.

### Shared rate limiter — enforced in code, not by memory

Rule 8 (1 req/sec/domain, honest User-Agent, respect `robots.txt`) is implemented
as **one shared limiter object that every outbound fetch passes through.** No
caller may bypass it.

An unattended retry loop that forgets politeness is how you get IP-banned from a
news site overnight, and a ban is not recoverable by fixing code.

```
User-Agent: Aakasavani/1.0 (personal news reader; +mailto:deepugudapati123@gmail.com)
```

`robots.txt` is fetched once per domain per day and cached.

---

## 7. Cost

| Item | Monthly |
|---|---|
| RSS, GDELT DOC, Wayback, Guardian, HN, arXiv, Finnhub, CoinGecko | **$0** |
| GDELT BigQuery (partitioned queries) | **$0** within 1 TB free tier |
| Trafilatura extraction (self-hosted) | $0 |
| Storage, Internet Archive snapshots | $0 |
| **Research panel** — Claude Haiku 4.5, on explicit request only | **$5–6** |
| VPS | $5–10 |
| **Total** | **$10–16** |

The research panel is the **only** LLM spend in the system, and it runs only when
the user clicks. There is no LLM anywhere in the reading path.

---

## 8. Build order

**This is the single authoritative build order.** Detail for each step lives in
`EDITION-AND-UI.md`; that document must not restate the order.

| # | Step | Notes |
|---|---|---|
| 01 | **Feed audit** | **Not code.** Fetch every feed once, record which ship `<content:encoded>`, switch to per-section URLs. Populates `feeds` |
| 02 | **Fixtures + test harness** | **Prerequisite for autonomy.** `fixtures/`, `conftest.py`, frozen clock, temp DB. See §12 |
| 03 | **`tests/test_rules.py`** | All Ten Rules as assertions. Must be red before any feature exists, green after |
| 04 | SQLite schema + migrations | `seen`, `read`, `feeds`, `editions`, `edition_items`, `topics`, `ia_queue` |
| 05 | Rate limiter + fetcher | shared limiter, honest UA, `robots.txt` cache, 3-step text fallback |
| 06 | Feed parser + dedupe | canonicalise, hash, `content:encoded` handling |
| 07 | **Edition build job** | poll → dedupe → select front page → **pre-fetch** → **atomic swap** |
| 08 | Feed view | headline + outlet blurb, section chips, hero/thumbnail images |
| 09 | Article view | **instant**, from pre-fetched text. Images inline. Logs `dwell_seconds` |
| 10 | Topic chips | saved FTS5 queries, user-editable |
| 11 | Internet Archive queue | inside the build, async, 6/min |
| 12 | TTL sweep + nightly backup | |
| 13 | Past editions | `GET /edition/YYYY-MM-DD` |
| 14 | Budget wrapper | `BudgetExceeded`, ledger, caps. **Before any LLM step** |
| 15 | Research panel — **Ask** tab | summarise + questions, lazy. **First LLM use** |
| 16 | Research panel — **Timeline** tab | GDELT DOC 2.0 chronology |
| 17 | Research panel — **Explain** tab | highlight-to-explain |
| 18 | Top-up job | every 30 min from 05:00, headlines only |
| 19 | FTS5 search over `read` | personal reading history |
| 20 | Deep history | BigQuery, Guardian API |
| 21 | Ranking | uses `dwell_seconds` logged since step 09 |
| 22 | Mobile | Phase 3. Same API, different client |

**Steps 01–09 are the product.** A finished edition, filterable, opening
instantly. Ship that, use it for two weeks, then decide whether 10–22 are still
what you want.

**Steps 02 and 03 are not optional and cannot be reordered.** They are the oracle.
A loop without them produces an agent that ticks every box and ships something
broken.

---

## 9. Explicitly not in this architecture

Recorded so they stay decided rather than quietly creeping back in:

- ❌ AI summaries of any kind in the feed
- ❌ Cross-article synthesis, claim extraction, truth adjudication
- ❌ Framing/perspective comparison across outlets
- ❌ Deep research agent (multi-source report generation)
- ❌ Story threading with read-position tracking
- ❌ Vector embeddings / semantic search — FTS5 is sufficient
- ❌ Permanent archive of unread ingested articles
- ❌ Multi-user support
- ❌ Todo list or calendar — Phase 2, see `ROADMAP.md`
- ❌ Ranking beyond recency + hand-written source weight

**In scope, and not to be confused with the above:** the research panel
(step 15–17) answers questions about the currently open article on explicit
request. It is a chat interface, deliberately, and it is the sole LLM in the
system. The rule it obeys is **pull, not push** — nothing is generated until the
user asks. See `EDITION-AND-UI.md` Part 3.

---

## 10. Operational mechanics

### TTL — Time To Live

The term is from networking: a counter that decrements until the data is
discarded. Here it is a column plus a scheduled job — **nothing expires
automatically in SQLite.**

```sql
-- on insert
expires_at = unixepoch() + 2592000        -- 30 days

-- daily sweep (cron): strip text, keep the hash forever
UPDATE seen
   SET title = NULL, description = NULL, source = NULL, expired = 1
 WHERE expires_at < unixepoch() AND expired = 0;
```

**Why 30 days:** the TTL must outlast how long an article stays in its source
feed, or an expired row reappears as "new." Feeds carry 20–100 items — a day or
two for a busy outlet. 30 days is a safe margin at negligible cost.

**Why strip rather than delete:** a hash is 32 bytes. Retaining every hash ever
seen costs ~9 MB/year and gives permanent "have I seen this?" memory. Deleting
the row loses that for no meaningful saving.

### SQLite configuration

```sql
PRAGMA journal_mode = WAL;      -- concurrent reads during writes
PRAGMA synchronous = NORMAL;    -- safe with WAL, much faster
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

Single writer (the build job) and single reader process. WAL removes the only
realistic locking scenario.

### Backup — configure on day one

`read` is the only irreplaceable data in the system. Everything else can be
re-fetched from the internet.

```bash
sqlite3 /app/aakasavani.db ".backup /backups/$(date +%F).db"
# retain 30 days, sync off-box
```

Use `.backup`, not `cp` — it handles an in-flight write correctly.

### Cron

```
0 4 * * *       /app/build-edition     # the edition build
*/30 5-23 * * * /app/topup             # headlines only
0 3 * * *       /app/sweep-ttl
30 2 * * *      /app/backup
```

Internet Archive endpoints, auth and rate limits: see `SOURCES.md` §4.

---

## 11. Documentation retirement

**These documents describe a system that does not exist yet. They are a plan, not
documentation, and plans go stale.**

Once build step 09 lands and there is a working edition:

| Section | Fate |
|---|---|
| §3 schema | **Delete.** Migrations become the truth |
| §4 data flows | **Delete.** Code becomes the truth |
| §10 mechanics | **Delete.** Config becomes the truth |
| §0 principles, §5 failure handling, §9 not-in-scope | **Keep.** Code cannot express *why* |
| `EDITION-AND-UI.md` Parts 1–3 | Shrink to rationale only |

Code is more trustworthy than prose about code. Every mature repo has a `docs/`
folder full of lies because nobody performs this step. Record the cut in
`logs/SESSIONS.md` when it happens.

---

## 12. Testing — the oracle

**A loop needs an oracle: something that answers "is this done?" without a human
in the room.** Without one you get an agent that runs for four hours, ticks every
box, and ships something broken.

Everything in this section exists to be that oracle. It is a **prerequisite for
autonomous building**, not a follow-up task — which is why it is build steps
02 and 03.

### 12.1 The Ten Rules as assertions

A rule that lives only in markdown drifts within a month. A rule that fails CI
does not. All ten convert:

| Rule | Test in `tests/test_rules.py` |
|---|---|
| 1 · No AI text in reading path | `test_no_llm_import_in_render_path` — static: no Anthropic client reachable from feed/article render<br>`test_stored_description_is_verbatim` — `seen.description` equals the parsed RSS `<description>`, byte-for-byte, **at storage** — see below<br>`test_render_sanitisation_only_removes_markup` — the HTML allowlist sanitiser may strip tags but must never alter, reorder, or reword surviving text |
| 2 · No cross-article synthesis | `test_six_outlets_six_entries` — one story across six feeds yields six rows |
| 3 · Articles whole and unaltered | `test_stored_text_equals_extractor_output` — no post-processing between Trafilatura and `read.full_text` |
| 4 · AI is pull, not push | `test_build_makes_zero_llm_calls` — the 04:00 job never calls Anthropic |
| 5 · TTL firehose, keep reads | `test_sweep_strips_text_keeps_hash`<br>`test_read_rows_never_expire` |
| 6 · Pre-fetch, never at click | `test_no_network_on_reading_path` — the *reading* handlers (`/`, `/edition/*`, `/article/*`) make no outbound HTTP; `/research/*` is the sole named exception, matching Rule 4 — see below |
| 7 · Never an empty page | `test_failed_build_keeps_previous_edition`<br>`test_swap_is_atomic` — killed mid-build leaves the old edition live |
| 8 · Never evade bot detection | `test_rate_limiter_is_shared_and_enforced`<br>`test_user_agent_is_honest`<br>`test_robots_txt_respected` |
| 9 · Log `read_at` / `dwell_seconds` | `test_read_schema_has_dwell_columns`<br>`test_article_view_writes_dwell` |
| 10 · SQLite, single process | `test_no_forbidden_dependencies` — psycopg2, redis, celery, pinecone, chromadb absent |

`tests/test_rules.py` runs on **every** verify, for every step, forever.

**Rule 1, "byte-for-byte," scopes to storage, not render.** RSS descriptions
routinely carry HTML entities and markup. Measured directly against
`feedparser` 6.0.14: it decodes entities during parsing, so `&amp;` on the wire
already becomes `&` before any application code sees the string — byte-for-byte
identity with the wire bytes is unsatisfiable at render time by any
implementation, not just an unlucky one. The rule's actual intent — no AI
rewording — is captured by asserting storage is verbatim from the parser, plus a
second test that sanitisation only ever removes markup. `logs/SESSIONS.md`
D-1/S-006.

**Rule 6 names `/research/*` as an explicit exception**, not a hole in the test.
Taken completely literally the rule would forbid the research panel outright,
since it is a request handler that calls Anthropic and GDELT by design — that
is Rule 4's entire premise. Scoping the assertion to the three reading routes
and asserting `/research/*` is the *only* route permitted network access is
stricter than an unscoped test would be: network access appearing anywhere
else fails immediately. `logs/SESSIONS.md` D-2/S-006.

### 12.2 Fixtures — tests never touch the network

This project is network-dependent, which makes live tests nondeterministic. A
feed returning 503 at 02:00 reads as a code failure, triggers a replan, and
rewrites working code. That failure mode loops forever.

**Record these before autonomy. Pathological cases matter more than happy paths:**

```
fixtures/
├── feeds/
│   ├── with_content_encoded.xml     full article body in the feed
│   ├── without_content_encoded.xml  description only
│   ├── malformed.xml                broken XML — parser must not crash
│   └── empty.xml                    valid, zero items
├── articles/
│   ├── normal.html                  extracts cleanly
│   ├── paywall_stub.html            200 OK, <500 chars — must be treated as failure
│   ├── consent_wall.html            200 OK, GDPR interstitial
│   ├── js_shell.html                200 OK, no body content
│   └── cloudflare_403.html          the block page
├── gdelt/artlist.json, empty.json
├── wayback/available_hit.json, available_miss.json
└── robots/permissive.txt, restrictive.txt
```

`scripts/record_fixtures.py` regenerates them reproducibly. Re-record when a feed
changes format — a stale fixture is a lie that passes.

**`tests/conftest.py` provides fixtures only and must guarantee:**

- **No network.** Patch the HTTP client at session scope; any real connection
  attempt raises.
- **Frozen clock.** The edition build depends on "now" — 04:00 IST boundaries,
  TTL expiry, top-up windows. Inject the clock; never call `datetime.now()`
  directly in application code.
- **Fresh temp DB per test.** Never the real database.

`tests/test_live.py` is the single exception — real network, run manually, never
part of the autonomous verify chain.

### 12.3 Red-first — a test never seen failing is not an oracle

**Every acceptance test must be observed failing before the feature exists.**

Write the test, run it, confirm it fails *for the expected reason* — not an
import error, not a typo — then implement. A test that has only ever been green
proves nothing; it may assert nothing at all.

This is the single cheapest defence against the failure mode where the loop
reports twenty passing requirements and the app doesn't work.

### 12.4 Verify chain

Run in order, stop at first failure:

```
1. python -c "import app"          does it even load
2. pytest tests/test_rules.py      the Ten Rules — always all of them
3. pytest tests/test_<step>.py     this step's acceptance criteria
4. pytest -x                       full suite, nothing regressed
```

---
