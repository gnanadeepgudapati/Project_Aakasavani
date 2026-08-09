# Project Aakasavani

A personal news reader. **Single user. Not a product. Not multi-tenant.**

Wake at 07:00 IST → open one web page → a finished edition is waiting, already
built and pre-fetched at 04:00 → read → done.

Topics: **Tech / AI / dev · Finance & markets · World & India news.**

---

## The four documents

Four files, three different jobs. They are **not** read the same way.

| File | Role | When |
|---|---|---|
| `docs/ARCHITECTURE.md` | **SPEC — authoritative** | Constantly. Build from this. Diagram, schema, data flows, failure handling, **build order (§8)**, operational mechanics |
| `docs/EDITION-AND-UI.md` | **SPEC — authoritative** | Constantly. 04:00 build, atomic swap, categories, images, research panel. Supplies *detail*; §8 supplies *sequence* |
| `docs/SOURCES.md` | **REFERENCE — look up** | When wiring a feed or API. Feed URLs, GDELT/Guardian/Wayback endpoints, content rights. **§1 feed list is FROZEN** |
| `docs/AUTONOMOUS-LOOP.md` | **PROCESS** | Before and during any unattended run. Preconditions, loop phases, exit conditions |
| `docs/ROADMAP.md` | **GUARD RAIL** | When a feature feels tempting. It will usually say "Phase 2" |

**If any document contradicts `docs/ARCHITECTURE.md`, ARCHITECTURE.md wins.**
Report the contradiction rather than silently choosing.

There is one build order, in `ARCHITECTURE.md` §8. Do not create a second one.

### Documentation is disposable

These documents describe a system that **does not exist yet**. They are a plan,
not documentation. After build step 5, most of the *what* becomes redundant with
code and must be deleted — see `ARCHITECTURE.md` §11. Code is more trustworthy
than prose about code.

Four documents were already deleted for describing rejected features. **A
superseded spec is worse than no spec** — an agent can build the wrong thing in
good faith and cite a project file as justification. When something is
superseded, delete it and record why in `logs/SESSIONS.md`. Never leave it around
marked "old".

---

## The ten rules

These were each arrived at by rejecting a more complicated alternative. They are
not preferences. **Do not quietly relax them.**

1. **No AI-generated text in the reading path.** Feed shows the outlet's own
   headline and description, verbatim from RSS. Never a generated summary.
2. **No cross-article synthesis.** No merging coverage, no claim extraction, no
   deciding what is true. Six outlets on one story means six entries.
3. **Articles are shown whole and unaltered.** Never rewritten, condensed, or
   reframed.
4. **AI is pull, not push.** The only LLM in the system is the research panel, and
   only when the user explicitly clicks. Nothing is generated in advance except
   starter questions.
5. **TTL the firehose, keep the reads.** `seen` expires after 30 days (text
   stripped, hash kept forever). `read` is permanent.
6. **Pre-fetch at 04:00, never at click time.** The user must never wait for a
   network fetch.
7. **Never show an empty page.** If the build fails, yesterday's edition stays up.
   Atomic swap only on success.
8. **Never evade bot detection.** No proxy rotation, no fingerprint spoofing, no
   headless evasion. Honest User-Agent, respect `robots.txt`, 1 req/sec/domain.
9. **Log `read_at` and `dwell_seconds` from day one.** Unused now. Cannot be
   generated retroactively.
10. **SQLite, single file, single process.** No Postgres, no Redis, no message
    broker, no vector database, no build pipeline.

---

## Explicitly NOT in Phase 1

Each was considered and rejected. **If you find yourself building one of these,
stop and ask.**

- ❌ AI summaries in the feed
- ❌ Cross-article synthesis / truth adjudication / "unified article"
- ❌ Framing comparison across outlets
- ❌ Deep research agent
- ❌ Story threading with read-position tracking
- ❌ Vector embeddings or semantic search (FTS5 is sufficient)
- ❌ Permanent archive of unread articles
- ❌ Multi-user support, accounts, auth beyond a single password
- ❌ Todo list or calendar (Phase 2 — see `docs/ROADMAP.md`)
- ❌ Mobile app (Phase 3)
- ❌ Ranking beyond recency + a hand-written source weight

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.12** | Trafilatura and feedparser are Python; no reason to fight it |
| Web | **FastAPI** | Async fetching, simple, no ceremony |
| Templates | **Jinja2, server-rendered** | Page must be instant. No SPA, no build step |
| JS | **Vanilla, minimal** | Only the panel and filters need it. No React |
| DB | **SQLite + FTS5**, WAL mode | Single user. One file. Backup is `cp` |
| Extraction | **Trafilatura** | F1 ≈ 0.945, best open-source article extractor |
| Feeds | **feedparser** | Handles the RSS/Atom mess |
| Scheduling | **cron** | Not Celery, not Airflow |
| LLM | **Claude Haiku 4.5** — `claude-haiku-4-5-20251001` | Research panel only. No Sonnet tier in Phase 1 — `logs/SESSIONS.md` S-004 |

Challenge this in planning if you have a real argument. Do not change it silently
mid-build.

---

## Project files you must maintain

Update these **as you work**, not at the end. A crash at hour three should lose
minutes, not the session.

| File | When to write to it |
|---|---|
| `CONTEXT.md` | One page: what exists, what's next, where you left off. **Read first in every session.** Rewritten, never appended |
| `REQUIREMENTS.md` | Checkboxes with `verify:` commands. **Generated after plan approval**, not before |
| `BLOCKED.md` | Anything you need from the user. In autonomous mode this replaces asking |
| `logs/ERRORS.md` | Every error, its cause and fix. Newest first, index at top. **Check here before debugging anything** |
| `logs/SESSIONS.md` | **Architectural changes only.** Decision, what it replaced, reasoning |
| `plans/NN-<step>.md` | One plan per build step, written before code |

No `PROGRESS.md` — `git log` is already one.

**`logs/SESSIONS.md` is the important one**, with one binding rule: **when a
SESSIONS entry contradicts a doc, patch the doc in the same commit.** SESSIONS
holds the *why*; the doc holds the *what*. A decision log that lets the
authoritative docs stay wrong defeats its own purpose.

---

## Verification — nothing is done until an oracle says so

**"Done" is an executable check, never the judgement of the agent that wrote the
code.** An agent grading its own homework always passes itself.

- A `REQUIREMENTS.md` box is ticked **only** when its `verify:` command exits 0.
- A requirement with no `verify:` line is a wish. Give it a command or cut it.
- **Red-first:** every acceptance test must be observed failing, for the expected
  reason, before the feature exists. A test only ever seen green proves nothing.
- The Ten Rules live in `tests/test_rules.py` and run on **every** verify.
  Mapping in `ARCHITECTURE.md` §12.1.
- **Tests never touch the network.** Fixtures only. `tests/test_live.py` is the
  single manually-run exception.

Verify chain, stop at first failure:

```
1. python -c "import app"        2. pytest tests/test_rules.py
3. pytest tests/test_<step>.py   4. pytest -x
```

---

## Autonomous session constraints

Full protocol: `docs/AUTONOMOUS-LOOP.md`. These constraints bind in **every**
mode.

**FORBIDDEN — no exceptions, no "just this once":**

- Editing anything under `tests/` or `fixtures/` during a BUILD phase. A test
  that looks wrong is a `BLOCKED.md` item, not an edit.
- Deleting, skipping, `xfail`-ing, or loosening an assertion to get green.
- Ticking a `REQUIREMENTS.md` box without its `verify:` command exiting 0.
- Weakening a Ten Rules check for any reason.
- Building anything on the DO-NOT-BUILD list. Encountering one is BLOCKED, not a
  design decision to make alone.
- Network calls in tests.
- Changing the frozen feed list (`SOURCES.md` §1) mid-run.
- `git push`, force-push, history rewrite, or branch deletion.

If the only way forward violates one of these, **that step is BLOCKED**: log it,
`git reset` it, skip it, continue with independent steps.

Without these constraints the fastest path to a green suite is editing the tests,
and an unattended agent will find that path.

---

## Working style

- **Plan before building.** Show the plan, wait for approval. Every step gets a
  `plans/NN-<step>.md` before any code.
- **Small steps.** Ship step N fully working before starting N+1.
- **Test the ugly paths.** 403s, dead links, paywall stubs, empty extractions,
  failed builds. These are the normal case, not the exception.
- **Retries are capped.** Attempt 1 fix the code, attempt 2 the *plan* is
  suspect, attempt 3 escalate. Uncapped loops on a wrong plan are the main way
  this wastes money.
- **Raise, don't route around.** Supervised: ask. Autonomous: `BLOCKED.md`.
- **No placeholder data.** If a feed isn't wired up, the page shows nothing, not
  lorem ipsum.

## Session start — every time

Read `CONTEXT.md`, then `logs/SESSIONS.md`, then `REQUIREMENTS.md`. State where
the project is and what's next. Then continue.

**Never resume from memory of a previous conversation.**

---

## Definition of done for Phase 1

The user wakes at 07:00 IST, opens one page, and finds a finished edition of
~40 articles built at 04:00. Filtering by section and topic works. Clicking any
article opens the full text instantly with no network wait. The research panel
answers questions about the open article on request. Nothing on the page was
written by an AI unless the user asked for it.
