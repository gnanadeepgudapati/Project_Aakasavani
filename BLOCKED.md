# BLOCKED

Things needed from the user. In autonomous mode this file replaces asking.

**Newest first. Resolved items move to the bottom under RESOLVED with a date.**

---

## FINAL REPORT — 2026-08-09

`AUTONOMOUS-LOOP.md` exit condition fired: **every `REQUIREMENTS.md` box is
ticked with a passing verify.** Written per that document's format.

### What shipped

All 88 requirements, steps 01–19 — the entire currently-planned scope.
Steps 01–09 ("the product," `ARCHITECTURE.md` §8) through step 19 (search),
including the full research panel (Ask/Timeline/Explain), budget wrapper,
Internet Archive queue, TTL sweep, backups, and top-up job. All 19 Ten Rules
tests individually demonstrated catching a real violation (`plans/99-final-
violation-pass.md`). Full suite: 92/92 green. 9 architectural decisions
recorded (`logs/SESSIONS.md` S-001…S-008, plus this session's approval note).

### What didn't ship, and why that's correct, not incomplete

**Steps 20–22** (deep history, ranking, mobile) — `ROADMAP.md`'s own gate:
"ship 01–09, live with it two weeks, then decide." No requirements exist for
them; building them now would be opening a gate that isn't mine to open.

**Nothing has run against real data.** The whole suite is fixture/mock-based
by design (`ARCHITECTURE.md` §12.2) — correct for a test suite, but it means
no one has watched a real 04:00 build run yet.

### What's needed from you, in priority order

1. **Nothing is required to keep the code correct** — it's fully tested as
   it stands.
2. **To actually run it**, in order of when each would first bite:
   - **B-001/B-003 resolved**: dev is Python 3.14 (verified working). Deploy
     target is still an open, low-stakes choice — install 3.14 on the VPS,
     or pin to Ubuntu 24.04's system 3.12 there (untested on 3.12 so far).
   - **B-002**: `ANTHROPIC_API_KEY` (paid, ~$5-6/mo) is the only credential
     the *code* needs to actually answer a research-panel question for real.
     `IA_S3_ACCESS_KEY`/`SECRET`, `GUARDIAN_API_KEY` are free but also unset.
   - **B-004**: 7 of the 35 frozen feeds were unreachable at the step-01
     audit. Still true, still not substituted, per `SOURCES.md` §1.
3. **A decision, not a requirement**: whether/when to deploy and start
   living with it, per `ROADMAP.md`'s two-week suggestion before considering
   steps 20+.

---

## OPEN

### B-007 · Front-page content quality — three problems visible in the first real edition

**Raised:** 2026-08-09, after the first real build. **Blocks:** nothing.
**Needed:** product decisions. All three are *mine to fix once you choose* —
none require changing the frozen feed list.

**1. Economic Times is a general feed filed under `finance`.** Its frozen URL
is `rssfeedstopstories.cms` — top stories, not markets. So Finance currently
carries cricket ("Australia top WTC table"), politics ("Govt extends ED
Director's tenure"), and US politics. 5 of Finance's 13 slots come from it.
`feeds.section` is **our** assignment, not the outlet's (S-001), so moving it
to `world_india` is not a frozen-list change. Livemint/Business Standard/The
Hindu-business remain genuine finance feeds.
**Recommendation: reassign Economic Times → `world_india`.**

**2. One high-frequency feed dominates each section.** Recency-only ranking
means whoever publishes most wins: Lobsters took 7 of 13 tech slots, The
Hindu — national took 9 of 13 world_india. `EDITION-AND-UI.md` calls the
ranking "deliberately dumb" and defers tuning until `dwell_seconds` exists —
but a per-feed cap (say max 3–4 per section) is a one-line change that
doesn't require any ranking intelligence.
**Recommendation: add a per-feed cap. Ranking beyond that stays deferred.**

**3. Lobsters entries make poor lead stories.** The current tech hero is
"postmarketOS in 2026-07: libcamera 0.7.2" with the description "Comments" —
Lobsters' RSS `<description>` is often just a link label. Fixing #2 largely
fixes this by accident. A `source_weight` bump for editorial outlets is the
in-spec lever (`EDITION-AND-UI.md`: "hand-edit the source weights when the
front page looks wrong"); all 35 are still at the default 3.

---

### B-006 · Article body renders raw Markdown syntax

**Raised:** 2026-08-09. **Blocks:** nothing, but it is visible on every article.

`app/extract/article.py` pins Trafilatura to `output_format="markdown"`, and
`article.html` renders that string as pre-wrapped plain text — so readers see
literal `**TechCrunch Mobility**` and `*Welcome back…*`.

Three options, and this needs a decision because **Rule 3 ("articles shown
whole and unaltered") constrains it**: (a) render the Markdown to HTML at
display time — the text is unchanged, only presented, which I read as
compatible with Rule 3 the same way `sanitize_description` is; (b) switch the
extractor to `output_format="txt"` — changes what is *stored*, and would need
R-005 re-verified; (c) leave it.
**Recommendation: (a), rendered at display time only.**

---

### B-005 · A feed that returns 200 with malformed XML never auto-disables

**Raised:** 2026-08-09 by the Track A agent, correctly escalated rather than
decided unilaterally. **Blocks:** nothing.

The Print and Scroll.in return real HTTP 200 with unparseable XML
(feedparser `bozo=1`, zero entries). `parse_feed`'s contract is "never raise
on malformed XML", so this is indistinguishable from "success, no new items"
— `fail_count` never increments, so unlike a 403/404 feed these are **never
auto-disabled** and will be polled forever. `ARCHITECTURE.md` §5's failure
table only names "404 / timeout", so extending "failure" to cover
persistently-bozo-with-zero-entries is a **spec change**, not a bug fix.
Locked in with a regression test (R-109) documenting current behaviour.

**Recommendation:** count "200 + bozo + zero entries" as a failure for
`fail_count` purposes, and patch `ARCHITECTURE.md` §5 in the same commit.

---

### B-004 · 7 of the 35 frozen feeds are unreachable — step 01 audit result

> **Partially stale as of 2026-08-09's real run.** Only **5** feeds actually
> fail at the HTTP level: Business Standard, PIB, Moneycontrol (403), AP,
> Anthropic news (404). The Print and Scroll.in **are reachable** — they
> return 200 with malformed XML, which is a different problem, now tracked
> separately as **B-005**.

**Raised:** 2026-08-09, step 01 (`scripts/audit_feeds.py`, live run against the
real internet)
**Blocks:** nothing — the other 28 feeds work, and `ARCHITECTURE.md` §5 already
specifies degraded handling for a dead/blocked feed. Flagged per `SOURCES.md`
§1's explicit instruction: **"do not silently swap in another."**
**Needed from user:** nothing required to keep building. Optional — if you know
a fix for any of these (e.g. the correct current URL), say so and I'll treat
it as an architectural change, logged in `logs/SESSIONS.md`, not a silent edit.

| Feed | URL | Section | Result | Likely cause |
|---|---|---|---|---|
| Business Standard | `https://www.business-standard.com/rss/home_page_top_stories.rss` | finance | `403` | Bot-blocking. Matches `SOURCES.md` §6's warning about Cloudflare default-blocking mixed-use crawlers |
| PIB (govt. releases) | `https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3` | world_india | `403` | Same — government sites are commonly behind aggressive WAFs |
| Moneycontrol | `https://www.moneycontrol.com/rss/latestnews.xml` | finance | `403` | Same |
| AP — top | `https://apnews.com/hub/ap-top-news.rss` | world_india | `404` | URL likely stale. AP has changed RSS paths before; the frozen URL may predate a restructure |
| Anthropic news | `https://www.anthropic.com/news/rss.xml` | tech | `404` | Same — `/news/rss.xml` returns 404; the feed may have moved or been retired |
| The Print | `https://theprint.in/feed/` | world_india | malformed (`bozo`, 0 entries) | feedparser couldn't parse a valid item — possibly a redirect to a non-RSS page, or a schema change |
| Scroll.in | `https://scroll.in/feed` | world_india | malformed (`bozo`, 0 entries) | Same |

**What I did, and deliberately didn't do:** recorded the failure in
`data/feeds.yaml` (`_audit_status`, `has_full_text: null`) and stopped — no
retries beyond the one built-in timeout retry, no header spoofing, no trying a
different URL pattern to "fix" the 404s. Guessing a replacement URL would be
exactly the silent substitution `SOURCES.md` §1 forbids, and working around a
403 would cross into the bot-detection evasion Rule 8 forbids outright.

**Effect on the section counts:** `world_india` and `finance` each lose some
real capacity until/unless these are resolved — 5 of the 17 `world_india` feeds
and 3 of the 9 `finance` feeds are currently down. `tech` is least affected (1
of 9). Not a blocker for steps 02–09, since the pipeline is built to handle a
reduced or failing feed set (`ARCHITECTURE.md` §5) — worth knowing before
judging the front page's variety once step 07 ships, though.

---

### B-003 · Deployment Python version — install 3.14 on the VPS, or pin to 3.12 there?

**Raised:** 2026-08-09
**Blocks:** nothing in steps 01–21. Deployment only.
**Needed from user:** A or B, whenever deployment planning starts — not now.

Residual of B-001. Dev now runs 3.14 (`CLAUDE.md` § Stack, `logs/SESSIONS.md`
S-005). Ubuntu 24.04's system Python is 3.12.

| Option | Notes |
|---|---|
| **A. Install 3.14 on the VPS** (deadsnakes PPA or pyenv) | Matches dev exactly. A few extra minutes of server setup |
| **B. Pin the deploy venv to 3.12** | Uses the system Python as-is. Re-verify the wheel stack on 3.12 before relying on it — not yet tested, only 3.14 has been |

No recommendation yet — low stakes, revisit near step 22 (deployment).

---

### B-002 · Credentials required before their build steps

**Raised:** 2026-08-08, planning session
**Blocks:** 01 (partially), 11, 14, 15–17, 20
**Needed from user:** the values below, in a `.env` file at repo root

| Variable | Needed for | Step | Free? | Where to get it |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | Research panel — the only LLM in the system | 14–17 | No, ~$5–6/mo | `console.anthropic.com` |
| `IA_S3_ACCESS_KEY` | Internet Archive Save Page Now | 11 | Yes | `archive.org/account/s3.php` |
| `IA_S3_SECRET_KEY` | ditto | 11 | Yes | ditto |
| `GUARDIAN_API_KEY` | Deep history, Guardian Open Platform | 20 | Yes, 5k/day | `open-platform.theguardian.com/access` |
| `AAKASAVANI_PASSWORD` | Caddy HTTP basic auth | deploy | — | Choose one |

**None of these block steps 02–09** — the product ships without any of them.
Only `ANTHROPIC_API_KEY` is a paid service, and it is not needed until step 14.

**Note on step 01:** the feed audit itself needs no credentials. It is listed
above only because a `.env.example` should be committed alongside it.

---

## RESOLVED

### B-001 · Python version — spec said 3.12, machine has 3.14.3 and 3.13

**Raised:** 2026-08-08 · **Resolved:** 2026-08-09, by measurement, approved as
part of plan approval.

Original worry: `CLAUDE.md` pinned 3.12; only 3.14.3/3.13 are installed, and
`lxml` (via Trafilatura) is a compiled dependency that could lack a 3.14 wheel
and fall back to a source build requiring MSVC. **Tested instead of assumed:**

```
python 3.14.3 | lxml 6.1.1 | trafilatura 2.2.0
              | feedparser 6.0.14 | fastapi 0.141.1

content:encoded extracted        OK
absent content -> getattr None   OK
malformed XML survived (bozo=1)  OK, 1 entry, no crash
extraction with images           OK, 803 chars, <img> preserved
paywall stub -> 18 chars         OK, correctly <500 = failure
```

Whole stack installs from binary wheels and runs. 3.14 has been out long enough
that the ecosystem caught up; the original wheel-availability concern was
stale. `CLAUDE.md` § Stack now records 3.14 for dev (`logs/SESSIONS.md` S-005).
Residual deployment-only question tracked separately as **B-003**.
