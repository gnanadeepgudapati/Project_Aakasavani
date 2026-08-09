# 00b — Real data + full page: the plan

**Status: AWAITING APPROVAL. Planning session, 2026-08-09 (Opus). No code
written in this session.**

Companion to `plans/00-implementation-plan.md`, which planned steps 01–19.
That plan was executed and all 88 of its requirements passed. This plan
exists because **passing all 88 did not produce a working product**, and the
reason is worth stating precisely before proposing fixes.

---

## 0. Why 92 passing tests produced a page showing fake data

One root cause, repeated eleven times: **every component was built and tested
in isolation against an injected fake, and the assembly that wires them
together for a real run was never built or tested.**

`ARCHITECTURE.md` §12.2 mandates "tests never touch the network" — correct,
and I followed it. But the corollary was never noticed: if every test injects
a fake fetcher, a fake `call_fn`, a hand-seeded `feeds` table, then *nothing
anywhere* exercises the real wiring. `REQUIREMENTS.md` had 88 entries and not
one of them said "the assembled system runs once, for real."

The project's own design anticipated this. `plans/00-implementation-plan.md`
§1 names `tests/test_live.py` — "MANUAL ONLY. Never in the verify chain" — as
the single real-network exception, precisely to catch this class of gap. **It
was never written.** No `REQUIREMENTS.md` line demanded it, so it stayed a
line in a plan document.

Everything below is a consequence of that one omission.

---

## 1. Verified defects — the pipeline cannot pull real data

Each was confirmed by reading the code this session, not recalled.

| # | Defect | Where | Consequence on a real run |
|---|---|---|---|
| **D-1** | **No `feeds.yaml` → `feeds` table sync exists at all** | nothing in `app/` | `poll_all_feeds` iterates an empty table. **Zero feeds polled, silently.** Every test hand-inserted feed rows |
| **D-2** | **`poll_all_feeds` has no error handling** | `build.py:36` | One dead feed raises and **kills the entire build**. 7 of 35 feeds are known dead (`BLOCKED.md` B-004), so this fails 100% of the time, immediately |
| **D-3** | **Feed polling bypasses the shared rate limiter** | `build.py:31` imports `_default_http_get` directly; that function never calls `limiter.acquire()` | **Rule 8 violation on the real path.** 35 feeds hit as fast as the loop runs. R-034 only ever tested the *article* fetch path, never the *feed* path |
| **D-4** | **Conditional GET never implemented** | `feeds.etag` / `last_modified` columns exist, are never read or written | §2.1's "cuts bandwidth ~95%" doesn't happen. Every poll is a full download |
| **D-5** | **`fail_count` / `enabled` never updated** | nothing writes them | §5's "disable after 10 consecutive failures" is unimplemented. Dead feeds are retried forever |
| **D-6** | **`robots_cache` not wired into the real `Fetcher`** | `build.py:63` — bare `Fetcher()`, so `robots_cache is None` and the check is skipped | **Rule 8 violation on the real path.** The logic is correct and tested (`test_fetcher.py` passes `robots_cache=`) but production never passes it |
| **D-7** | **`og:image` never extracted** | `resolve_description(page_html=...)` supports it; no caller passes `page_html` | Images come only from RSS `media:*` tags. Many feeds ship none → a largely image-less front page, despite §6 being a whole document section |
| **D-8** | **`read_minutes` never computed** | `atomic_swap` accepts it, `run_build` never passes it | Always `NULL`. Cosmetic, but it's in the schema and the spec |

## 2. Verified gaps — the page is missing Phase-1 features that ROADMAP promises

`ROADMAP.md` Phase 1 lists these as in-scope. The **backends exist and are
tested**; the **UI and routes do not exist at all**:

| # | Feature | Backend | Route | UI | ROADMAP Phase 1? |
|---|---|---|---|---|---|
| **G-1** | Research side panel (Ask/Timeline/Explain) | ✅ `app/research/*`, 4 endpoints | ✅ | ❌ **nothing in `article.html`** | ✅ named explicitly |
| **G-2** | Topic chips | ✅ `app/topics.py` | ❌ **none** | ❌ **none** | ✅ named explicitly |
| **G-3** | Search over reads | ✅ `app/search.py` | ❌ **none** | ❌ **none** | step 19, built |
| **G-4** | Density toggle (Compact/Comfortable/Visual) | ❌ | ❌ | ❌ | ✅ named explicitly, `EDITION-AND-UI.md` §6.5 |

R-062…R-064 tested `topics.py`'s *functions*. R-080…R-085 tested the research
*endpoints*. R-088 tested `search_read()`. **Not one tested that a human can
reach any of it.** Same root cause as §0.

---

## 3. The plan

Two tracks. **Track A needs nothing from you and produces real news on the
page.** Track B makes the page match what `ROADMAP.md` already promises.
Track C is deployment and is the only part needing money or accounts.

`ARCHITECTURE.md` §8 is the single build order and steps 20–22 are reserved
(deep history, ranking, mobile). This plan proposes **amending §8 to add
steps 23–27**, logged as S-009, rather than inventing a parallel build order
— `CLAUDE.md` forbids two build orders.

### Track A — make it pull real data

**Step 23 · Feed registry sync + poll hardening** — fixes D-1…D-5
- `app/registry.py`: `sync_feeds_to_db(conn)` — upsert from `feeds.yaml` by
  URL, **preserving** existing `etag`/`last_modified`/`fail_count` on rows
  that already exist (a naive delete-and-reinsert would throw away all
  conditional-GET state every run)
- `poll_all_feeds`: per-feed `try/except`; increment `fail_count` on failure,
  reset to 0 on success, set `enabled = 0` at 10 consecutive; **a failing
  feed must never abort the build**
- Conditional GET: send `If-None-Match`/`If-Modified-Since` from stored
  values, handle `304` as "no new items, not an error", store returned
  `ETag`/`Last-Modified`
- **Route feed polling through the shared limiter** — this is the Rule 8 fix

**Step 24 · Fetcher wiring + metadata completeness** — fixes D-6…D-8
- Build a real `RobotsCache` (fetch through the limiter, 1-day TTL) and pass
  it into `Fetcher()` in `prefetch_front_page` — the Rule 8 fix for articles
- Extract `og:image` from the page bytes already fetched during pre-fetch
  (no extra request — the response is in hand), fill `seen.image_url` when
  the feed gave none
- Compute `read_minutes = ceil(total_words / 220)` and pass to `atomic_swap`

**Step 25 · Operational entrypoints + the missing live test**
- `scripts/run_build.py`, `run_topup.py`, `run_sweep.py`, `run_backup.py` —
  each a thin CLI wrapper, `--db` flag, exit codes
- **`tests/test_live.py`** — the file `plans/00-implementation-plan.md`
  promised and never delivered. Manual only, excluded from `pytest`'s default
  run, hits the real network: polls one real feed, extracts one real article,
  asserts the shape. This is the test that would have caught D-1…D-6

**Step 26 · First real run + triage**
- Run `scripts/run_build.py` against the real 35 feeds, watch it, and fix
  what reality breaks. Expect: encoding surprises, unparseable dates,
  redirect chains, feeds that 200-with-garbage. Fixtures cannot predict these
- Deliverable is a **real edition on the page** plus an honest record of what
  the fixtures had missed

### Track B — make the page full-fledged

**Step 27 · UI completion** — fixes G-1…G-4
- **Research side panel** — right-docked ~40%, article reflows to 60%,
  three tabs, resizable, width in `localStorage` (`EDITION-AND-UI.md` §3.1).
  Wires the 4 endpoints that already exist and currently nothing can call
- **Topic chips** — second chip row, `+ new` box, `GET /?topic=`, backed by
  `app/topics.py`; seed the 4 topics from `EDITION-AND-UI.md` §2.2
- **Search page** — `GET /search?q=`, over `read` only
- **Density toggle** — three modes, `localStorage`, default Comfortable

### Track C — deployment (needs your resources)

**Step 28 · Deploy**
- Hetzner CX22 (or equivalent), Ubuntu, Caddy + TLS + HTTP basic auth
- cron: build 04:00, top-up :30 05:00–23:00, sweep 03:00, backup 02:30
- Decide the prod Python version (`BLOCKED.md` B-003)

---

## 4. What I need from you

**For Track A — real news on the page — I need nothing.** No API keys, no
accounts, no money. RSS is public, Wayback's lookup API is keyless,
Trafilatura runs locally. This is the important part: *the thing you actually
asked for has no external dependency.*

**Track B needs nothing either**, except `ANTHROPIC_API_KEY` if you want the
research panel to actually answer (the panel UI can be built and shown
degrading gracefully without one).

| Resource | Needed for | Cost | Blocking? |
|---|---|---|---|
| — | **Track A: real data** | **$0** | **No — start now** |
| `ANTHROPIC_API_KEY` | Research panel answers | ~$5–6/mo | Only for G-1's live answers |
| `IA_S3_ACCESS_KEY` + `SECRET` | Internet Archive snapshots | free | Only step 11's live use |
| `GUARDIAN_API_KEY` | Deep history (step 20, unplanned) | free | No |
| VPS + SSH | Track C | ~€4/mo | Only for deployment |
| Domain (optional) | Track C TLS | ~$10/yr | No — IP works |
| `AAKASAVANI_PASSWORD` | Caddy basic auth | — | Only for deployment |

### Two decisions I should not make alone

1. **The 7 dead feeds** (`BLOCKED.md` B-004 — Business Standard, PIB,
   Moneycontrol 403; AP, Anthropic 404; The Print, Scroll.in malformed).
   `SOURCES.md` §1 is frozen and forbids silent substitution. Options: leave
   them (they'll fail, `fail_count` up, auto-disable at 10 — harmless once
   D-2/D-5 are fixed), or replace them (an architectural change needing a
   SESSIONS entry). **Recommendation: leave them for the first real run**, so
   we see genuine failure handling working, then decide with real data.

2. **"Override code 0 0 0 0"** — I don't know what this meant, so I've
   assumed nothing by it. I have **not** relaxed any of the Ten Rules,
   because they're the project's whole thesis and two of the defects above
   (D-3, D-6) are Rule 8 violations I'm proposing to *fix*, not waive. If you
   meant something specific by it, tell me.

---

## 5. Estimated shape of the work

| Step | New requirements (est.) | Risk |
|---|---|---|
| 23 · registry sync + poll hardening | ~8 | Low — clear spec |
| 24 · fetcher wiring + metadata | ~5 | Low |
| 25 · entrypoints + `test_live.py` | ~4 | Low |
| 26 · first real run + triage | ~3 | **High — this is where reality bites, and the point** |
| 27 · UI completion | ~10 | Medium — the panel is the biggest single piece |
| 28 · deploy | ~5 | Medium, and gated on your resources |

Roughly 35 new requirements. Steps 23–26 are the ones that answer "why is my
page showing the same news as yesterday."

## 6. What I will NOT do without you saying so

- Change `SOURCES.md` §1's frozen feed list
- Relax, skip, or weaken any of the Ten Rules or their tests
- Build anything on `ARCHITECTURE.md` §9's DO-NOT-BUILD list
- Build steps 20–22 (deep history, ranking, mobile) — `ROADMAP.md`'s
  ship-and-live-with-it gate still stands
