# SESSIONS

**Architectural changes only.** Decision · what it replaced · reasoning · the doc
patched in the same commit.

Routine work does not go in here. `git log` is the progress log. Filling this
file with "wrote the parser" destroys the one thing it is for: finding out *why*
something is the way it is, six months later, when the reasoning is gone.

**Binding rule: when an entry here contradicts a doc, patch the doc in the same
commit.** SESSIONS holds the *why*; the doc holds the *what*. A decision log that
lets the authoritative docs stay wrong defeats its own purpose.

---

## 2026-08-09 · Steps 23–27, built by two parallel agents

### S-009 · Steps 23–28 added to the build order; 8 defects + 4 UI gaps closed

**Decided:** `ARCHITECTURE.md` §8's build order is extended with steps 23–28
(registry sync + poll hardening, fetcher wiring + metadata, operational
entrypoints, first real run, UI completion, deploy). Not a second build
order — `CLAUDE.md` forbids that — an amendment to the existing one.

**Replaces:** the implicit assumption that steps 01–19 completing meant the
product worked.

**Reasoning:** all 88 requirements passed and the app could not pull real
data at all. Root cause: every component was tested in isolation against an
injected fake, and the assembly was never built or tested.
`tests/test_live.py` — named in `plans/00-implementation-plan.md` from the
first planning session as the guard against exactly this — was never
written, because no `REQUIREMENTS.md` line demanded it. Full analysis in
`plans/00b-real-data-and-ui-plan.md` §0.

**Two of the eight defects were Rule 8 violations on the real path**: feed
polling bypassed the shared limiter entirely (`_default_http_get` called
directly), and `robots_cache` was never passed to the production `Fetcher`.
Both had correct, tested logic that production simply did not use. R-097 and
R-100 are new Ten-Rules tests that exercise the **real default wiring** with
nothing injected — the class of test that would have caught them originally.

**Method:** two agents in isolated git worktrees, disjoint file ownership and
requirement-ID ranges (A: R-089…R-110, B: R-111…R-130), merged with zero
conflicts. Bookkeeping files were withheld from both and reconciled here.

**Verified:** 139 tests pass; a real build against the 35 frozen feeds
produced a live 39-article edition (1,931 `seen` rows, 60 sources, 34/39
pre-fetched, 36/39 with images, `read_minutes=182`), with 5 dead feeds
failing gracefully without aborting.

**Docs patched:** `ARCHITECTURE.md` §8 (steps 23–28), `REQUIREMENTS.md`
(R-089…R-130), `CONTEXT.md`, `BLOCKED.md`.

---

## 2026-08-09 · Approval to build (Prompt 2 start)

User approved `plans/00-implementation-plan.md` and said "start the build,"
without individually re-litigating R-7/R-8 and D-1…D-4 — each already carried a
concrete, evidence-backed recommendation in that plan. Adopted as written.
Recorded here rather than silently applied, per the same reporting obligation
that produced S-001…S-004.

---

## 2026-08-09 · Build session, steps 07-08 (edition build, feed view)

### S-008 · Rule 6 scopes to the front page; "show everything" fetches on click by design

**Decided:** the reading-path network ban (Rule 6, `test_no_network_on_
reading_path`) applies to **front-page articles** — the ones `seen.full_text`
was pre-fetched for. Opening a "show everything" (below-the-fold) article,
which was never pre-fetched, is allowed to fetch live at click time.

**Replaces:** nothing textually — this is a real contradiction between
`CLAUDE.md`'s Rule 6 ("Pre-fetch at 04:00, never at click time... the user
must never wait for a network fetch," stated with no carve-out) and
`ARCHITECTURE.md` Flow B (explicitly: "else live fetch → Trafilatura" as the
click-time path for a not-yet-`read` article) and `EDITION-AND-UI.md`'s own
"DECIDED" edition shape ("full ingest... fetched on click, not pre-fetched").
Found while implementing step 08/09's routes, not noticed during planning.

**Reasoning:** the two-tier "front page (instant) + full ingest (on click)"
shape is a deliberate, load-bearing design decision (S-003 sizes the front
page around exactly this split), confirmed independently in two documents.
Rule 6's actual purpose — the *primary* reading experience must never wait —
is satisfied by guaranteeing the front page's ~39 articles are always
pre-fetched; it was never a promise that literally every article in the full
ingest opens instantly, and `EDITION-AND-UI.md` says so explicitly, in the
open. Per `CLAUDE.md`'s own precedence rule, `ARCHITECTURE.md` (and the
corroborating `EDITION-AND-UI.md`) wins over an unqualified reading of Rule 6.

**Docs patched:** none — `CLAUDE.md` Rule 6's wording already permits this
reading if "at click time" is understood as "for an article the build
promised would be instant," but the ambiguity is worth recording so it isn't
mistaken for a violation later. `tests/test_rules.py::test_no_network_on_
reading_path` is written to test exactly this scope: pre-fetched articles
never touch the network on open; a not-yet-fetched one legitimately may.

---

### S-007 · `seen` gets `full_text`/`fetched_via`; pre-fetched text does not go in `read`

**Decided:** front-page pre-fetched text is stored on `seen.full_text` /
`seen.fetched_via` (migration `002_seen_prefetch.sql`), populated only for
the ~39 front-page items. `read` gains a row only when the user actually
opens an article, exactly as before.

**Replaces:** nothing explicit — this is a genuine gap the original §3 draft
and `plans/00-implementation-plan.md` §2 both missed, surfaced while
implementing step 07's pre-fetch phase, not a contradiction between docs.

**Reasoning:** `EDITION-AND-UI.md` §1.3 says pre-fetched text is "already in
SQLite" before the user opens it — but `read` is defined as **permanent** and
"what you actually opened" (`CLAUDE.md` Rule 5, `ARCHITECTURE.md` §3). Writing
full text into `read` for all ~39 front-page articles regardless of whether
they're ever opened would be exactly the "permanent archive of unread
articles" `ROADMAP.md` rules out explicitly, and would make `dwell_seconds`/
`read_at` meaningless placeholders for rows nobody read. `seen` already
expires in 30 days and Rule 5 already establishes it holds text that later
gets stripped ("TTL the firehose... text stripped") — extending that same
row with pre-fetched full text keeps the cache naturally bounded by the
existing TTL, with no new eviction mechanism needed. The daily sweep now
also nulls `full_text`/`fetched_via` alongside the existing stripped columns.

**Docs patched:** `ARCHITECTURE.md` §3 (`seen` schema), §10 (sweep SQL, both
copies — there were two, only one was originally caught and fixed).

---

### S-006 · Rulings on D-1 through D-4

**D-1 — Rule 1 "byte-for-byte" scopes to storage, not render.** Measured
directly (not assumed) with feedparser 6.0.14: it decodes HTML entities during
parsing, so `&amp;` on the wire is already `&` before any app code runs.
Byte-for-byte identity with the wire bytes is unsatisfiable at render by any
implementation. `test_feed_description_is_verbatim` is replaced by
`test_stored_description_is_verbatim` (storage) plus
`test_render_sanitisation_only_removes_markup` (an allowlist sanitiser may
strip tags but never reword). Patched `ARCHITECTURE.md` §12.1.

**D-2 — Rule 6 excludes `/research/*` by name.** Taken literally the rule
forbids the research panel outright, since it is a request handler that calls
Anthropic and GDELT by design — Rule 4's entire premise. Renamed the test
`test_no_network_on_reading_path`, scoped to `/`, `/edition/*`, `/article/*`,
and asserting `/research/*` is the *only* route with network access — stricter
than an unscoped test, since access appearing anywhere else now fails
immediately. Patched `ARCHITECTURE.md` §12.1.

**D-3 — `robots.txt` disallow blocks the Wayback fallback too.** Was unstated.
Recovering a publisher's page from a public archive after their own
`robots.txt` asked us not to take it defeats the point of honouring `robots.txt`
at all. Patched `ARCHITECTURE.md` §5 (failure-handling table).

**D-4 — deleted the standalone 15-minute ingest worker.** `ARCHITECTURE.md`
§2.1 described one; nothing else in the document supports it — the cron table
in §10 lists only build/top-up/sweep/backup, and the whole `EDITION-AND-UI.md`
thesis is that the continuous river was replaced by a scheduled edition. A
15-minute cadence would triple fetch volume against the 35 frozen feeds for no
user-visible benefit, straining Rule 8. Patched `ARCHITECTURE.md` §2.1.

**Docs patched:** `ARCHITECTURE.md` §5, §2.1, §12.1 (two rows plus explanatory
notes).

---

### S-005 · Fixed broken cross-references and the "ship line" contradiction

**Renumbered `ARCHITECTURE.md`'s "Documentation retirement" section 13 → 11.**
The document's own numbering was broken — sections ran 0…10, jumped straight to
13, then printed 12 *after* 13 physically. §11 never existed. `CLAUDE.md` had
already been citing "`ARCHITECTURE.md` §11" for this section; renumbering makes
that existing citation correct rather than editing CLAUDE.md to match a broken
number.

**"Ship steps 1–5" → "ship steps 01–09."** `CLAUDE.md`, the (now-renumbered)
`ARCHITECTURE.md` §11, and `ROADMAP.md` all said step 5. `ARCHITECTURE.md` §8 —
the sole authoritative build order — says "Steps 01–09 are the product" and
defines why: 08 is the feed view, 09 is the article view logging
`dwell_seconds`. Step 5 alone is a rate limiter and fetcher with no edition, no
feed view, and no article view — not a usable product by `CLAUDE.md`'s own
definition of done ("opens one page, finds a finished edition... clicking any
article opens the full text instantly"). §8's reasoned statement wins over the
three passing "step 5" mentions elsewhere. Patched `CLAUDE.md`, `ARCHITECTURE.md`
§11, `ROADMAP.md`.

**Fixed two more stale step numbers:** the research panel was called "step
9–11" in `ARCHITECTURE.md` §9 — panel steps are actually 15–17 (14 is the
budget-wrapper prerequisite). And `EDITION-AND-UI.md` said `dwell_seconds` is
"logged from step 4" — step 04 only adds the *column*; nothing writes to it
until the article view, step 09.

**Python stack recorded as 3.14 (dev), prod deferred.** See `BLOCKED.md` B-001:
lxml/trafilatura/feedparser/fastapi all install as binary wheels and run
correctly on 3.14.3, measured directly. The only real open question — dev 3.14
vs. Ubuntu 24.04's system 3.12 — is a deployment-time decision nothing in steps
01–21 depends on, so it is deferred rather than blocking. Patched `CLAUDE.md`
§ Stack.

**Docs patched:** `ARCHITECTURE.md` (§13→§11 heading, §9, §11 body),
`CLAUDE.md` (disposability note, § Stack), `ROADMAP.md`,
`EDITION-AND-UI.md` (front-page ranking note).

---

## 2026-08-08 · Planning session (Prompt 1)

Four contradictions were found between the governing documents. `CLAUDE.md` says
to report them rather than silently choose, so all four were put to the user and
closed by them. No code was written this session.

---

### S-004 · Research panel pins Haiku 4.5; no Sonnet escalation tier

**Decided:** all research-panel calls use `claude-haiku-4-5-20251001`.

**Replaces:** the unversioned string "Claude Haiku" in `CLAUDE.md` § Stack and
`ARCHITECTURE.md` §7, plus the optional *"think harder" → Sonnet* control
floated in `EDITION-AND-UI.md` §3.5.

**Reasoning:** "Claude Haiku" is a family, not a callable identifier — the API
needs an exact model ID, so leaving it unpinned is an open decision, and
`AUTONOMOUS-LOOP.md` precondition 1 forbids starting with one. The Sonnet tier
was self-described as optional, appears in no build step (15–17 are Ask,
Timeline, Explain), and is absent from the "No open questions" table, i.e. it was
never actually promoted to a decision. It also strains the `SINGLE_CALL_CAP` of
$0.10 far harder than Haiku does. Nothing depends on it, so it bolts on later
without rework.

**Docs patched:** `CLAUDE.md` § Stack, `ARCHITECTURE.md` §7,
`EDITION-AND-UI.md` §3.5 and its "No open questions" table.

---

### S-003 · Front page is ~40 articles at 13 per section, not 8

**Decided:** front page = top **13 per section × 3 sections ≈ 40**.

**Replaces:** `EDITION-AND-UI.md`'s "top 8 per section", and its DECIDED block
reading "top 8 per section × 5 sections".

**Reasoning:** direct arithmetic consequence of S-002. "Top 8" was never an
independent decision — it was 40 ÷ 5 sections. Once sections drop to 3, holding
"8" fixed silently shrinks the edition to 24 and breaks `CLAUDE.md`'s definition
of done ("a finished edition of ~40 articles"). Of the two numbers, ~40 is the
one stated as the definition of done, and `CLAUDE.md` outranks
`EDITION-AND-UI.md`. Pre-fetch volume and Internet Archive load are unchanged
from the original spec, since both were sized against 40, not against 8.

**Docs patched:** `EDITION-AND-UI.md` §"Selection — front page ranking" and the
DECIDED block.

---

### S-002 · Phase 1 ingest is RSS only — the 35 frozen feeds, nothing else

**Decided:** the ingest worker polls **only** the RSS feeds in `SOURCES.md` §1.

**Replaces:** the SOURCES box in `ARCHITECTURE.md` §1's system diagram, which
reads `~120 RSS feeds · GDELT DOC · HN · arXiv · Reddit · GitHub · Finnhub ·
CoinGecko`.

**Reasoning:** that box contradicts the frozen list on two counts. It says ~120
feeds where §1 contains 35, and it lists five APIs that appear nowhere in §1.
`SOURCES.md` §1 is marked FROZEN and `ARCHITECTURE.md` §8's step 01 is defined as
auditing *that list*. The §5 supplementary APIs are reference material for later
phases. Hacker News needs no separate integration — it is already in the frozen
list as `hnrss.org`. GDELT remains in scope but only in Flow C (research panel,
on demand), never in the 15-minute ingest loop.

**Docs patched:** `ARCHITECTURE.md` §1 SOURCES box.

---

### S-001 · Three sections, not five

**Decided:** `section` ∈ `{tech, finance, world_india}`.

**Replaces:** three mutually inconsistent taxonomies across the docs —
`EDITION-AND-UI.md` §2.1's five (`tech · business · world · india · science`),
`ARCHITECTURE.md` §3's four (`tech | finance | world | india`), and
`CLAUDE.md`'s three.

**Reasoning:** `CLAUDE.md` is binding and states three topics; where documents
disagree the ordering is CLAUDE.md, then ARCHITECTURE.md, then the rest. The
five-section model is also unbuildable as written — no feed in the frozen list
carries a `science` or `business` label, so two of its five sections would render
permanently empty, violating Rule 7 in spirit. The 35 frozen feeds map onto three
sections cleanly, with the finance-flavoured Indian outlets (Livemint markets and
companies, Economic Times, Business Standard, The Hindu business, Moneycontrol)
assigned to `finance` rather than `world_india`:

| Section | Feeds |
|---|---|
| `tech` | 9 |
| `finance` | 9 |
| `world_india` | 17 |

Note this makes `feeds.section` a **column the project assigns**, not one
inherited from the outlet's own section naming — the per-section feed URLs still
supply the accuracy, but the mapping to our three buckets is ours.

**Docs patched:** `EDITION-AND-UI.md` §2.1, `ARCHITECTURE.md` §3 schema comment
on `seen.topic` (also renamed `topic` → `section`, per `EDITION-AND-UI.md` §2.1's
own instruction, which had never been applied to the §3 schema).
