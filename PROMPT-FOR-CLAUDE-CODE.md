# Prompts for Claude Code

Three prompts, used in this order. **Do not skip to 3.**

| # | Prompt | When |
|---|---|---|
| 1 | **Planning** | Once. No code is written |
| 2 | **Supervised build** | Steps 01–03, with you watching |
| 3 | **Autonomous** | Only after 2 completes cleanly |

The order is not ceremony. Prompt 2 exists because **the first run always reveals
a `verify:` command that verifies nothing.** Discovering that while watching costs
minutes; discovering it at 6am after an unattended run costs the night.

---

# PROMPT 1 — Planning session

Open this folder in Claude Code and paste everything in the box.

```
We are building Project Aakasavani — a personal news reader for one user (me).

STOP. Do not write any application code in this session. This session is
PLANNING ONLY. I want a plan I can review and approve before a single line of
the app gets written. If you find yourself creating app/, models.py, or
anything importable, you have drifted — stop and return to planning.

═══════════════════════════════════════════════════════════════
STEP 1 — READ
═══════════════════════════════════════════════════════════════

Read these in order and confirm you have done so:

  CLAUDE.md                    ← binding rules. Not preferences.
  docs/ARCHITECTURE.md         ← the build spec. Authoritative.
  docs/EDITION-AND-UI.md       ← build timing, categories, images, panel
  docs/SOURCES.md              ← feeds (FROZEN), endpoints, content rights
  docs/AUTONOMOUS-LOOP.md      ← the unattended protocol you will later run
  docs/ROADMAP.md              ← phase boundaries

Two are specs you build from (ARCHITECTURE, EDITION-AND-UI), one is reference
(SOURCES), one is process (AUTONOMOUS-LOOP), one is a guard rail (ROADMAP).

If any two disagree, docs/ARCHITECTURE.md wins. Report the contradiction
rather than silently picking one — I have already had three of these and they
are the main way this project can go wrong.

There are no open decisions. If you find one, that is a bug in the docs —
report it, because it blocks autonomous mode entirely.

═══════════════════════════════════════════════════════════════
STEP 2 — SCAFFOLDING
═══════════════════════════════════════════════════════════════

Create these now. Templates and rules are in CLAUDE.md.

  CONTEXT.md          one page: what exists, what's next, where you left off.
                      Rewritten each session, never appended. FIRST file you
                      read in every future session.

  BLOCKED.md          anything you need from me. In autonomous mode this
                      replaces asking.

  logs/ERRORS.md      every error, cause, fix. Newest first, index at top.
                      Checked BEFORE debugging anything.

  logs/SESSIONS.md    architectural changes ONLY. Decision, what it replaced,
                      reasoning, and the doc you patched in the same commit.
                      Routine work in here kills its usefulness.

  plans/              one plan per build step, written before code.

  .workflow/STATE.json   loop memory (template: docs/AUTONOMOUS-LOOP.md)
  .workflow/BUDGET.json  spend vs caps

  git init, and a .gitignore covering .workflow/, *.db, fixtures cache

NOT REQUIREMENTS.md — that comes after I approve the plan, or it is stale the
moment the plan alters build order.

NOT PROGRESS.md — git log is already one.

═══════════════════════════════════════════════════════════════
STEP 3 — PLAN
═══════════════════════════════════════════════════════════════

Produce an implementation plan covering:

  1. Repo layout — every file and directory you intend to create
  2. The exact SQLite schema you will run. docs/ARCHITECTURE.md §3 has a
     draft — improve it where it is wrong and tell me precisely what changed
  3. Build order. It is in docs/ARCHITECTURE.md §8 and ONLY there. Follow it
     unless you have a real reason not to. Do not create a second build order
     anywhere — two build orders is how a project builds the wrong thing in
     the right sequence.
  4. FOR EVERY PHASE-1 FEATURE: name the test that will prove it works.
     A feature with no named test does not go in the plan.
  5. How you will record fixtures (docs/ARCHITECTURE.md §12.2), including the
     pathological ones — 403, paywall stub, consent wall, malformed XML
  6. How you will convert all Ten Rules into tests/test_rules.py
     (mapping is given in docs/ARCHITECTURE.md §12.1)
  7. What I must provide before you can start: Anthropic API key,
     archive.org S3 credentials, Guardian API key, anything else
  8. Every risk or ambiguity you found in the docs
  9. Every place you disagree with the spec — now, not later

Note that build step 01 is NOT code: it is fetching each frozen feed once and
recording which ship full article text in <content:encoded>. Feeds that do
never need fetching again. Plan how you will run that audit.

Steps 02 and 03 — fixtures and test_rules.py — cannot be reordered or
deferred. They are the oracle. Everything after them depends on them.

═══════════════════════════════════════════════════════════════
THE TEN RULES — not preferences
═══════════════════════════════════════════════════════════════

Full text in CLAUDE.md. All ten become assertions in tests/test_rules.py.

  1. No AI-generated text anywhere in the reading path
  2. No cross-article synthesis — six outlets means six entries
  3. Articles shown whole and unaltered
  4. AI is pull, not push — research panel only, on explicit click
  5. TTL the firehose (30d, strip text keep hash), keep the reads (permanent)
  6. Pre-fetch at 04:00 IST, never at click time
  7. Never show an empty page — atomic edition swap only on success
  8. Never evade bot detection — shared limiter, 1 req/sec/domain, honest UA
  9. Log read_at and dwell_seconds from day one, though nothing uses them yet
 10. SQLite, single file, single process. No Postgres, Redis, or vector DB

═══════════════════════════════════════════════════════════════
DO NOT BUILD
═══════════════════════════════════════════════════════════════

Each was considered and deliberately rejected. Encountering one is a BLOCKED
item, not a design decision to make alone.

  ✗ AI summaries in the feed
  ✗ Cross-article synthesis, claim extraction, truth adjudication
  ✗ Deep research agent
  ✗ Story threading with read-position tracking
  ✗ Vector embeddings or semantic search — FTS5 is sufficient
  ✗ Permanent archive of articles I never opened
  ✗ Multi-user support or accounts beyond one password
  ✗ Todo list or calendar — Phase 2
  ✗ Mobile app — Phase 3
  ✗ Ranking beyond recency plus a hand-written source weight

═══════════════════════════════════════════════════════════════
OUTPUT FROM THIS SESSION
═══════════════════════════════════════════════════════════════

  - Confirmation you read all six documents
  - The scaffolding created, git initialised
  - The implementation plan
  - A named test for every Phase-1 feature
  - Your questions and disagreements

No application code. I approve the plan first.
```

---

# PROMPT 2 — Supervised build, steps 01–03

Only after you have approved the plan.

```
Plan approved. Generate REQUIREMENTS.md from it now.

Every checkbox gets an executable verify: command. Format:

  - [ ] R-012  Parser extracts <content:encoded> when the feed provides it
        verify: pytest tests/test_parser.py::test_content_encoded

A requirement with no verify: line is a wish, not a requirement — either give
it a command or move it out of Phase 1. A box is ticked ONLY when its verify
command exits 0. Never by judgement.

Then build steps 01, 02 and 03 ONLY, with me watching:

  01  feed audit          — fetch each frozen feed once, record has_full_text
  02  fixtures + harness  — fixtures/, conftest.py, frozen clock, temp DB,
                            no-network guard
  03  tests/test_rules.py — all Ten Rules as assertions

Follow the loop in docs/AUTONOMOUS-LOOP.md — PLAN, BUILD, VERIFY, COMMIT —
but stop after each step and show me:

  - the plan file before you write code
  - each new test failing first, and the reason it failed
  - the verify output

For step 03 specifically: prove each rule test actually detects a violation.
Break the thing it guards, show it going red, restore. A rule test that has
never caught anything is decoration.

Stop after step 03. Do not continue to 04.
```

---

# PROMPT 3 — Autonomous run

Only after prompt 2 completes and you have seen the rule tests catch real
violations.

```
Run autonomously from step 04. Follow docs/AUTONOMOUS-LOOP.md exactly.

Before starting, verify every precondition in that document and refuse to
start if any fails. Report which one.

I am not here. Do not ask me anything — use BLOCKED.md.

Check .workflow/STOP before every phase. If it exists, halt and summarise.

Caps: $2/day, $25/month, no single call above $0.10, enforced in code by the
budget wrapper — not by your own restraint.

Reminders, because these are what fail unattended:

  - Never fix a failing test by changing the test
  - Red-first: every acceptance test observed failing, for the right reason,
    before the feature exists
  - Retries capped at 3. Attempt 2 means the PLAN is suspect, not the code
  - A blocked step never blocks the run — reset it, skip it, continue
  - Patch the contradicted doc in the same commit as any SESSIONS entry
  - The feed list in docs/SOURCES.md §1 is frozen. A dead feed is a BLOCKED
    item, not a substitution

Stop and write a final report to BLOCKED.md when any exit condition fires:
all requirements ticked, STOP file present, all remaining steps blocked, a
budget cap exceeded, the same error signature three times across different
steps, or the full suite red for three consecutive commits.

Final report: what shipped, what didn't, what you need from me, priority
order.
```

---

## Kill switch

```bash
touch .workflow/STOP        # halts before the next phase
rm .workflow/STOP           # allows a resume
```

Checked before every phase. It will not interrupt an in-flight operation, so
allow up to a few minutes.

## Resuming any later session

```
Read CONTEXT.md, then logs/SESSIONS.md, then REQUIREMENTS.md.
Tell me where we are and what is next. Then continue.

Never resume from memory of a previous conversation.
```

---

## Folder structure this produces

```
Project_Aakasavani/
├── CLAUDE.md                  ← binding rules (auto-loaded every session)
├── PROMPT-FOR-CLAUDE-CODE.md  ← this file
├── CONTEXT.md                 ← where we left off. Read first
├── REQUIREMENTS.md            ← checkboxes with verify: commands
├── BLOCKED.md                 ← what the loop needs from you
├── docs/
│   ├── ARCHITECTURE.md        ← authoritative spec + build order §8 + oracle §12
│   ├── EDITION-AND-UI.md      ← build timing, categories, images, panel
│   ├── SOURCES.md             ← feeds (FROZEN), endpoints, rights
│   ├── AUTONOMOUS-LOOP.md     ← the unattended protocol
│   └── ROADMAP.md             ← phase boundaries
├── logs/
│   ├── ERRORS.md              ← every error and its fix
│   └── SESSIONS.md            ← architectural changes only
├── plans/NN-<step>.md         ← one per build step, before code
├── tests/
│   ├── test_rules.py          ← the Ten Rules as assertions
│   ├── conftest.py            ← fixtures only, no network
│   └── test_live.py           ← manual only, never in the verify chain
├── fixtures/                  ← recorded HTTP, incl. 403 / paywall / malformed
├── .workflow/                 ← STATE.json, BUDGET.json, STOP
└── app/                       ← the application
```

---

## Before you run prompt 3, check these yourself

The loop can only be as honest as its oracle. Verify by hand:

- [ ] `pytest tests/test_rules.py` passes, and you have **watched each rule test
      fail** when its rule is violated
- [ ] `pytest` runs with the network physically off
- [ ] `REQUIREMENTS.md` has a `verify:` command on every single line
- [ ] Budget wrapper raises before spending, not after — test it with a $0 cap
- [ ] `touch .workflow/STOP` actually halts the loop
- [ ] `git log` is clean and every commit names its requirement IDs

**Most of the value in this whole setup is the `verify:` commands and the
fixtures.** They make your review fast and reliable whether or not anything runs
unattended. The loop only spends tokens while you sleep.
