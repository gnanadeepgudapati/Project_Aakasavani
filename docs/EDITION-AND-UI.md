# Project Aakasavani — Edition Build, Categories & Research Panel

Extends `ARCHITECTURE.md`. Three additions:

1. **Scheduled overnight build** — a finished edition waiting when you wake
2. **Category filtering** — sections and topics, no classifier
3. **Research side panel** — AI on request, inside the article

---

## 0. The model shifts from river to edition

The app is no longer a continuously refreshing feed. It is a **daily edition**:
finite, complete before you wake, addressable by date.

| River | Edition |
|---|---|
| Infinite scroll, no bottom | Finite. You can finish it |
| Always behind | Complete when you open it |
| Fetch on click | **Pre-fetched overnight** |
| "What's new since I looked?" | "Today's paper" |

This is the better fit for the stated use: wake at 7am, read, done.

---

# Part 1 — The overnight build

## 1.1 Timing

**Recommended: 04:00 IST**, not 02:00.

IST is UTC+5:30, so:

| IST | ET | What has happened |
|---|---|---|
| 02:00 | 15:30 prev day | **US markets still open.** Misses the close |
| **04:00** | **17:30 prev day** | **US close (16:00 ET) + after-hours + evening cycle** |
| 05:00 | 18:30 prev day | Slightly more US evening news |

Since finance is one of the three topics, **04:00 IST captures the US market
close** and still leaves three hours before a 07:00 read. That margin matters —
the build is allowed to be slow.

**Plus incremental top-ups every 30 minutes after the build**, so genuinely
breaking news isn't absent at 07:00. Top-ups add headlines only; they do not
rebuild the edition.

## 1.2 What the build does

The build has hours available and no one waiting. Use that.

```
04:00  ── poll all feeds (conditional GET)
04:02  ── dedupe → canonicalise → hash
04:03  ── select edition (top N per section)
04:05  ── PRE-FETCH FULL TEXT for the whole edition   ← the big win
           · 1 req/sec/domain, spread over ~25 min
           · feed content:encoded → live fetch → Wayback
           · retry failures, fall back, retry again
04:30  ── queue every edition article to Internet Archive (6/min)
04:47  ── build FTS index, compute topic matches
04:50  ── ATOMIC SWAP: edition goes live
         (on failure: previous edition stays, quiet "last updated" note)
05:00+ ── top-up every 30 min, headlines only
```

## 1.3 Why pre-fetching is the highest-value change here

It falls out of the scheduling idea for free and fixes three separate problems:

| Problem | Solved how |
|---|---|
| 1–2 s wait on every article open | **Zero wait.** Text is already in SQLite |
| Cloudflare 403s (from 15 Sep 2026) | Failures occur at 04:00 with **hours of retry and Wayback fallback** before you'd see them |
| Internet Archive snapshots only on read | Every edition article archived overnight — including ones you never open |
| Dead links surfacing mid-read | Detected and resolved overnight |

**The access-rot problem largely stops being a user-facing problem.** It becomes
a background job's problem, at 4am, with time to recover.

### Volume and etiquette

Pre-fetching ~100 articles/night is more crawler-shaped than click-driven
fetching. Keep it defensible:

- **Pre-fetch the top 40–50 only**, not literally everything ingested
- 1 request/second per domain, spread across 20–30 minutes
- Honest descriptive User-Agent with a contact address
- Respect `robots.txt`
- Never parallel-hammer one host

Across ~40 domains this is comparable to one person browsing. That is a
defensible position; a burst of 500 parallel requests is not.

## 1.4 Atomic swap — do not wake up to an empty page

The most important failure case in the whole system, because it is the one you'd
experience personally at 07:00.

```sql
CREATE TABLE editions (
  id          INTEGER PRIMARY KEY,
  edition_date TEXT NOT NULL,          -- '2026-08-07'
  built_at    INTEGER,
  status      TEXT,                    -- building | live | failed
  article_count INTEGER,
  read_minutes  INTEGER
);

CREATE TABLE edition_items (
  edition_id  INTEGER,
  url_hash    BLOB,
  section     TEXT,
  rank        INTEGER,
  PRIMARY KEY (edition_id, url_hash)
);
```

Build into `status='building'`. Flip to `'live'` only on success, in one
transaction. The web app always serves the most recent `'live'` edition.

If the build fails: yesterday's edition remains, with a quiet
*"Last updated 06 Aug 04:00 — this morning's build failed"* note. Degraded, never
empty.

## 1.5 Implementation

A cron entry, not a job queue:

```
0 4 * * *      /app/build-edition
*/30 5-23 * * * /app/topup
0 3 * * *      /app/sweep-ttl
30 2 * * *     /app/backup
```

Single process, single machine. No Celery, no Airflow, no broker.

---

# Part 2 — Categories without a classifier

Two mechanisms, both free, both deterministic. **No LLM, no trained model.**

## 2.1 Sections — come free from the feeds

Nearly every outlet publishes **per-section RSS**. Subscribe to sections rather
than outlets and you get publisher-assigned categorisation, more accurate than
any model would guess, at zero cost.

```
https://www.thehindu.com/business/feeder/default.rss     → finance
https://www.thehindu.com/sci-tech/feeder/default.rss     → tech
https://indianexpress.com/section/india/feed/            → world_india
https://www.livemint.com/rss/markets                     → finance
https://feeds.bbci.co.uk/news/world/rss.xml              → world_india
https://feeds.arstechnica.com/arstechnica/index          → tech
```

Note the publisher's own section name is the *evidence*, not the label. The URL
tells us the outlet filed it under business or world; we map that onto our three
buckets. `feeds.section` is written once, by hand, at step 01.

The `feeds` table already carries a `topic` column — rename it `section` and it
becomes a fixed, reliable label written at ingest. (That rename is applied in
`ARCHITECTURE.md` §3 as of 2026-08-08.)

**Sections are three, fixed and stable:** `tech · finance · world_india`.

Per `CLAUDE.md`, which is binding and names exactly three topics. An earlier
five-value list here (`tech · business · world · india · science`) was
unbuildable — no feed in the frozen list carries a `science` or `business`
label, so two of the five would have rendered permanently empty. See
`logs/SESSIONS.md` S-001.

The 35 frozen feeds map on cleanly. Note the finance-flavoured Indian outlets
(Livemint markets and companies, Economic Times, Business Standard, The Hindu
business, Moneycontrol) belong to `finance`, not `world_india` — the section is
the *subject*, not the country:

| Section | Feeds |
|---|---|
| `tech` | 9 |
| `finance` | 9 |
| `world_india` | 17 |

## 2.2 Topics — saved queries, not stored tags

Topics like *energy*, *geopolitics*, *AI*, *semiconductors*, *elections* cut
across every section and every outlet. They should **not** be written onto
articles.

```sql
CREATE TABLE topics (
  id      INTEGER PRIMARY KEY,
  name    TEXT UNIQUE,             -- 'Energy'
  query   TEXT,                    -- FTS5 expression
  enabled INTEGER DEFAULT 1
);

INSERT INTO topics (name, query) VALUES
  ('Energy',      'oil OR gas OR OPEC OR solar OR renewable OR "power grid" OR coal'),
  ('AI',          '"artificial intelligence" OR LLM OR OpenAI OR Anthropic OR "machine learning"'),
  ('Geopolitics', 'sanctions OR treaty OR "border dispute" OR NATO OR tariff OR diplomatic'),
  ('Crypto',      'bitcoin OR ethereum OR crypto OR stablecoin OR blockchain');
```

Matching happens at query time against the FTS index:

```sql
SELECT s.* FROM seen s
  JOIN seen_fts f ON f.rowid = s.rowid
 WHERE seen_fts MATCH (SELECT query FROM topics WHERE name = 'Energy')
 ORDER BY s.published_at DESC;
```

### Why queries beat tags — this is the real argument

| Property | Saved query | Stored tag (classifier or LLM) |
|---|---|---|
| Add a new topic | **Retroactive instantly** — matches the whole history | Must reprocess every article |
| Understand why something matched | **Visible** — read the query | Opaque |
| Fix a bad match | **Edit one string** | Retrain, or write exceptions |
| Delete a topic | Delete a row | Orphaned tags everywhere |
| Cost | **$0** | Per-article inference |
| Wrong-but-confident matches | Impossible | Routine |

**You can tune topics yourself, see exactly why an article matched, and add a new
topic that immediately works on articles from six months ago.** No classifier
gives you that.

Start with 5–6 topics, refine as you use it. A topic that never gets clicked is
one row to delete.

## 2.3 In the UI

Two chip rows, combinable:

```
SECTIONS   [All] [Tech] [Finance] [World & India]
TOPICS     [AI] [Energy] [Geopolitics] [Crypto] [Elections] [+ new]
```

Selection persists in `localStorage`. `+ new` opens a box to type a query — the
whole topic system is user-editable at runtime.

---

# Part 3 — The research panel

## 3.1 Side panel, not popup — this matters

**Every question you'd ask is about the article.** A modal popup covers the
article, so it removes the thing you're asking about at the moment you ask.

| | Modal popup | **Side panel** |
|---|---|---|
| Article visible while asking | ✗ | **✓** |
| Reference the text mid-conversation | ✗ | **✓** |
| Highlight-to-explain | Broken — can't select | **✓** |
| Feels like | An interruption | A companion |

**Right-docked, ~40% width, article reflows to 60%. Resizable, width remembered.**

## 3.2 One panel, three tabs

Not three separate interfaces.

| Tab | Contents |
|---|---|
| **Ask** | *Summarise this article* button · seeded starter questions · free-form input |
| **Timeline** | GDELT chronology for this story (`ARCHITECTURE.md` Flow C) |
| **Explain** | Where highlight-to-explain results land |

## 3.3 Seeded questions — the detail that decides adoption

**Never show an empty input box.** Empty chat boxes go unused; three specific
clickable questions get clicked.

**DECIDED: generated lazily, on first panel open for that article — not at build
time.** Cached in `read.starter_questions` so a second open is free.

Reasoning: at build time you generate for 40 articles and open maybe 5, so ~87%
of the spend is wasted (~$0.08/night vs ~$0.01/day). More importantly it keeps
**all** LLM usage off the build path, which is what makes Rule 4 mechanically
testable — `test_build_makes_zero_llm_calls` asserts the 04:00 job never calls
Anthropic. Latency is irrelevant here: opening the panel is already an explicit
action, and ~1s is invisible against it.

Examples of the right shape:

> *What changed compared with the previous policy?*
> *Who is affected by this, and how many?*
> *Is anyone disputing these figures?*

Generic questions ("What is this about?") are worse than none. They must be
specific to the article.

## 3.4 AI scope — this is not a reversal

Worth stating plainly, since it sits beside a decision to have no AI:

| Where | AI? |
|---|---|
| Feed headlines and descriptions | **No.** Outlet's own words |
| Article body | **No.** Whole and unaltered |
| Chronology / timeline | **No.** Metadata from GDELT |
| **Research panel, on explicit request** | **Yes** |

The principle is **pull, not push.** Nothing is summarised, rewritten, or
interpreted before you ask. The AI is a tool you reach for inside an article, not
a filter between you and the news. The reading path stays exactly as decided.

## 3.5 Model and cost

| Use | Model | Tokens | Cost each |
|---|---|---|---|
| Summarise on request | Haiku | ~3k in / 200 out | ~$0.004 |
| Question turn | Haiku | ~5k in / 300 out | ~$0.007 |
| Highlight-to-explain | Haiku | ~1k in / 100 out | ~$0.002 |
| Starter questions (build time) | Haiku, batched | ~2k in / 80 out | ~$0.002 × 50/night |

At 10 summaries + 20 questions/day: **~$5–6/month.**

**Model is pinned: `claude-haiku-4-5-20251001`.** "Claude Haiku" is a family,
not a callable identifier, and an unpinned model is an open decision —
`AUTONOMOUS-LOOP.md` precondition 1 forbids starting the loop with one.

**The optional *"think harder"* → Sonnet control is NOT in Phase 1.** It was
never promoted to a decision: it appears in no build step (15–17 are Ask,
Timeline, Explain) and in no DECIDED table, and at ~$0.05 per use it strains the
$0.10 `SINGLE_CALL_CAP` far harder than Haiku does. Nothing depends on it, so it
bolts on later without rework. See `logs/SESSIONS.md` S-004.

**Grounding rule:** the panel answers from the article text plus, where relevant,
your own `read` history. Web search only on explicit request. Always cite which
paragraph an answer came from — a claim the panel can't point at is a claim you
shouldn't trust.

---

# Part 4 — Revised cost

| Item | Monthly |
|---|---|
| All data sources | $0 |
| Extraction, storage, Internet Archive | $0 |
| **Research panel (Haiku, on request)** | **$5–6** |
| VPS | $5–10 |
| **Total** | **$10–16** |

The panel is the only LLM spend in the system, and it only runs when you ask.

---

# Part 5 — Build order

**The build order lives in `ARCHITECTURE.md` §8 and only there.**

It is deliberately not restated here. Two copies of a build order in two
documents is how a project ends up building the wrong thing in the right order.

This document supplies the *detail* for those steps — timing, atomic swap,
category model, image treatment, panel behaviour. `ARCHITECTURE.md` supplies the
*sequence*.

---

# Part 6 — Images

## 6.1 Where images come from — free, already in hand

| Source | Field | Notes |
|---|---|---|
| RSS | `<media:content>`, `<media:thumbnail>`, `<enclosure>` | Present in many feeds |
| Any article page | `og:image` | Near-universal. Already fetched with the body |
| GDELT DOC artlist | social sharing image | Returned directly in the API response |
| Article body | inline `<img>` | Trafilatura extracts these with the text |

**No extra fetching, no new source, no cost.** The image URLs arrive with data
already being collected.

## 6.2 The case against full-bleed backgrounds

Considered and rejected: every article card carrying its photo as a background.

**Legibility.** News photography is unpredictable — bright skies, busy crowds, a
subject in a white shirt. Contrast behind text cannot be guaranteed. The standard
remedy is a dark gradient scrim, but applied across 40 cards every one resolves to
the same murky tone, erasing the visual variety the images were added for.

**Scanning speed.** The 07:00 task is triaging ~40 headlines. Text on a flat
background scans measurably faster than text over photographs. Image-dominant
layouts are *browsy* — built for leisurely discovery. A dense text list is built
for "what happened, what do I open." The second is what this product is for.

**Density.** Full-bleed cards need ~94px each and cannot fit the outlet's
description. Thumbnail rows fit the description and four articles in the space
three full-bleed cards occupy.

**Editorial images are selected to provoke.** A photograph beside a headline
changes how the headline reads before a word is processed. This project was built
on the principle that nothing sits between you and the source — no summaries, no
synthesis, no reframing. Images are the most emotionally loaded and least
informative element available. Making them the dominant visual makes them the
loudest voice on the page.

**Copyright is materially worse for images than text.** Reuters, AP and Getty
enforce photo licensing aggressively. `og:image` exists *to be* redistributed as a
link preview — thumbnail-sized and attributed is the intended use and defensible.
Stretched full-bleed as page design language is a weaker position.

## 6.3 Decision: images belong in the article, not decorating the index

| Location | Treatment |
|---|---|
| **Article view** | **Full images, inline, in publisher-placed positions.** Unambiguously correct — they are part of the piece |
| **Lead story, per section** | **One hero image.** Creates hierarchy, signals the day's big story, gives the page life |
| **All other list rows** | **~90px thumbnail beside the text**, never behind it |
| **No image available** | Row renders text-only. No placeholder, no grey box |

The hero-plus-thumbnail pattern is where every serious reader converged —
NetNewsWire, Reeder, Feedly — after trying the alternatives.

## 6.4 Gradient fade — images dissolve into text

Images do not stop at a hard rectangular edge. They fade out into the surrounding
text. **The amount of fade is inversely proportional to image size.**

| Element | Fade | Direction | Rationale |
|---|---|---|---|
| **Hero** | **Generous** — solid to ~46%, gone by 100% | Bottom edge, into the headline | Large enough that losing half still leaves a legible photograph. Standard editorial pattern |
| **Thumbnail** | **Light** — solid to ~75%, gone by 100% | Right edge, toward the text | Only 62px wide; a heavy fade destroys the image entirely |

### Why thumbnails get only a light feather

A fade consumes image area. At 62 × 46 px the picture is already working hard to
convey anything. Fading 60% of it leaves a smudge — decoration rather than
information — and news photography is unpredictable enough that the fade line
lands mid-subject as often as not. That is the full-bleed legibility problem
reproduced at small scale.

A 25% feather removes the boxy hard edge and preserves three quarters of the
picture. That is the whole benefit at almost none of the cost.

### Implementation — use `mask-image`, not an overlay gradient

**This matters and is easy to get wrong.**

```css
/* CORRECT — background-agnostic, works in light and dark themes */
.hero {
  -webkit-mask-image: linear-gradient(to bottom, #000 46%, rgba(0,0,0,.35) 82%, transparent 100%);
          mask-image: linear-gradient(to bottom, #000 46%, rgba(0,0,0,.35) 82%, transparent 100%);
}

.thumb {
  -webkit-mask-image: linear-gradient(to right, #000 74%, transparent 100%);
          mask-image: linear-gradient(to right, #000 74%, transparent 100%);
}
```

```css
/* WRONG — a gradient overlay in the page background colour */
.hero::after { background: linear-gradient(transparent, #fff); }
```

The overlay approach requires the gradient to match the page background exactly.
It breaks the moment you add a dark theme, change the background, or hover a row
with a highlight colour — the fade becomes a visible pale smear over the image.

`mask-image` removes pixels rather than painting over them, so whatever is behind
shows through correctly in every theme and state. Support is universal in current
browsers; keep the `-webkit-` prefix for Safari.

**Note:** masking makes the image edge genuinely transparent, so a row's hover
background will show through the faded region. That's correct and looks right —
but check it deliberately rather than discovering it later.

## 6.5 Density toggle

Three modes, persisted in `localStorage`:

| Mode | Behaviour |
|---|---|
| **Compact** | No images anywhere in the list. Fastest scan |
| **Comfortable** *(default)* | Hero on section leads, thumbnails elsewhere |
| **Visual** | Hero treatment throughout, for leisurely reading |

Cheap to build and it settles the argument empirically within a week instead of
theoretically now.

## 6.6 Implementation notes

- **Lazy-load everything below the fold** (`loading="lazy"`). The page must render
  instantly; images arrive after.
- **Constrain dimensions** in CSS so late-arriving images never reflow the list.
- **Hotlink rather than cache.** `og:image` is served precisely to be embedded
  elsewhere. Caching images locally is a heavier copyright question than text and
  buys nothing.
- **Handle referrer blocking** — some CDNs reject cross-origin hotlinks. On image
  error, collapse the element and fall back to text-only. Never show a broken icon.
- **Attribute** the source outlet on the hero image.
- **Bandwidth**: 40 thumbnails ≈ 400 KB. 40 full-bleed images ≈ 4–8 MB. Another
  reason the thumbnail default wins on a page meant to feel instant.

---

# DECIDED

## Build time: 04:00 IST

Captures the US market close (16:00 ET = 02:30 IST) plus after-hours and the US
evening cycle, and leaves three hours to pre-fetch before a 07:00 read.

Top-ups every 30 minutes from 05:00, headlines only.

## Edition shape: front page, with everything underneath

```
┌──────────────────────────────────────────┐
│  FRONT PAGE            ~39 articles      │
│  top 13 per section × 3 sections         │
│  fully pre-fetched at 04:00              │
│  finite — you can finish it              │
├──────────────────────────────────────────┤
│  ▾ Show everything (213 more)            │
│    full ingest, filterable by chips      │
│    fetched on click, not pre-fetched     │
└──────────────────────────────────────────┘
```

**Why this shape wins.** The front page preserves the thing that makes an edition
better than a river — it ends, and you can finish it. But on a day when something
big happens, nothing is thrown away; the full ingest is one click down. You get
completion by default and depth on demand.

**Two consequences for the build:**

1. **Pre-fetch only the front page** (~40 articles). The remainder keeps
   headline + outlet description and is fetched on click. This keeps overnight
   fetching modest and defensible — ~40 requests across ~40 domains over 25
   minutes.
2. **Internet Archive snapshots cover the front page only.** 40 articles at
   6/min ≈ 7 minutes. Everything below the fold archives on read, as before.

### Selection — front page ranking

Ranking is deferred everywhere else in this project, but the front page needs
*some* rule on day one. Start deliberately dumb:

```
per section, order by:
  1. published_at DESC        (recency)
  2. tie-break: source weight (a hand-written number per feed, 1–5)
take top 13
```

**13, not 8.** "Top 8" was never an independent decision — it was 40 ÷ 5
sections. Sections are now 3 (`logs/SESSIONS.md` S-001), so holding 8 fixed
would have silently shrunk the edition to 24 and broken `CLAUDE.md`'s definition
of done, which states ~40 articles. 13 × 3 = 39. See `logs/SESSIONS.md` S-003.

The source weight lives in `feeds.source_weight` (`ARCHITECTURE.md` §3),
defaulting to 3.

That's it. No engagement modelling, no scoring function. Hand-edit the source
weights when the front page looks wrong. Revisit only after `dwell_seconds` has
accumulated enough real data to justify something smarter — which is precisely
why it's being logged from step 4.

---

# No open questions

All Phase 1 decisions are closed. This is a precondition for autonomous building
— an unresolved decision means the agent either stalls or invents an answer and
builds on it.

| Question | Decision |
|---|---|
| Build time | **04:00 IST**, top-ups every 30 min from 05:00 |
| Edition size | **Front page ~39 — 13 × 3 sections**, full ingest one click below |
| Sections | **Three: `tech · finance · world_india`** |
| Ingest scope | **RSS only — the 35 frozen feeds. No arXiv/Reddit/GitHub/Finnhub/CoinGecko** |
| Research model | **`claude-haiku-4-5-20251001` only. No Sonnet tier** |
| Front-page ranking | **Recency, tie-broken by hand-written source weight 1–5** |
| Images | **Hero faded into headline, thumbnails 25% feather** |
| Past editions | **Browsable — `GET /edition/YYYY-MM-DD`** |
| Starter questions | **Lazy, on first panel open, cached** |
| Hosting | **Hetzner CX22, Caddy, HTTP basic auth, single password** |
| Feed list | **Frozen — `SOURCES.md` §1 is final for Phase 1** |

Adding a decision back into this document means autonomous mode must stop until
it is closed again.
