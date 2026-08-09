# Autonomous build protocol

**PROCESS — read in full before any unattended run.**

The core insight: an unattended loop needs an **oracle** — something that answers
*"is this done?"* without a human. Everything here serves that. A loop without an
oracle runs for hours, ticks every box, and delivers something broken.

---

## Preconditions — refuse to start until ALL hold

| # | Precondition | Where |
|---|---|---|
| 1 | **Every open decision closed** | `EDITION-AND-UI.md` "No open questions" |
| 2 | **Feed list frozen** | `SOURCES.md` §1 |
| 3 | **Fixtures recorded**, incl. 403 / paywall / malformed | `ARCHITECTURE.md` §12.2 |
| 4 | **`tests/test_rules.py` exists and passes** | `ARCHITECTURE.md` §12.1 |
| 5 | **Every requirement has a `verify:` command** | `REQUIREMENTS.md` |
| 6 | **Spend ceiling enforced in code** | `ARCHITECTURE.md` §6 |
| 7 | **Rate limiter shared and enforced in code** | `ARCHITECTURE.md` §6 |
| 8 | **User has watched 2 steps run supervised** | — |
| 9 | **`git status` clean, repo initialised** | — |

Precondition 8 is not ceremony. **The first run always reveals a `verify:`
command that verifies nothing.**

---

## Files

```
.workflow/STATE.json    loop memory; survives crashes and context compaction
.workflow/BUDGET.json   dollars + tokens + wall-clock spent vs caps
.workflow/STOP          kill switch — if this file exists, halt immediately
BLOCKED.md              questions for the user; the loop's substitute for asking
plans/NN-<step>.md      one plan per step, written before code
```

### `.workflow/STATE.json`

```json
{
  "current_step": "06-feed-parser",
  "phase": "VERIFY",
  "attempt": 2,
  "max_attempts": 3,
  "last_failure": "test_parser.py::test_content_encoded — AttributeError",
  "steps_complete": ["01-feed-audit", "02-fixtures", "03-rules", "04-schema", "05-fetcher"],
  "steps_blocked": [],
  "error_signatures": {"AttributeError:parser.py:44": 2},
  "started_at": "2026-08-08T04:00:00+05:30"
}
```

**Rewritten after every phase transition.** If the session dies or context
compacts, the next session reads this and knows exactly where it stands.

**Error signature** = `<ExceptionType>:<file>:<line of the top frame in our own
code>`. Three occurrences of the same signature across *different* steps means
something systemic is wrong → EXIT.

---

## The loop

**Do not ask the user anything mid-loop — they are not there.** `BLOCKED.md` is
the substitute.

**Before every phase: if `.workflow/STOP` exists, halt immediately and write a
summary.** Check every time, without exception.

### SELECT
Read `STATE.json`. Pick the next step whose dependencies are all in
`steps_complete` and which is not in `steps_blocked`. None remain → EXIT.

Verify `git status` is clean before proceeding. A dirty tree means the previous
step did not finish cleanly → investigate before continuing.

### PLAN
Write `plans/NN-<step>.md` **before touching code**:

- exact files to create or modify
- acceptance criteria, **named as the tests that will exist**
- which `REQUIREMENTS.md` IDs this closes
- which `docs/` sections it implements

No code in this phase.

### BUILD
Implement the plan, nothing beyond it.

**Red-first is mandatory.** Write each acceptance test, run it, and confirm it
fails *for the expected reason* — not an import error, not a typo. Only then
implement. A test that has only ever been green proves nothing.

Needing something not in the plan means **the plan was wrong** → REPLAN. Do not
improvise.

### VERIFY
Run in order, stop at first failure:

```
1. python -c "import app"          does it even load
2. pytest tests/test_rules.py      the Ten Rules — always all of them
3. pytest tests/test_<step>.py     this step's acceptance criteria
4. pytest -x                       full suite, nothing regressed
```

All green → COMMIT. Any red → FAIL.

### FAIL
Append to `logs/ERRORS.md`: the exact error, your diagnosis, what you tried.
Increment `attempt` and the error signature count.

| Attempt | Action |
|---|---|
| 1 | BUILD again, fixing the specific failure |
| 2 | **REPLAN** — the plan is suspect, not just the code. Rewrite `plans/NN-<step>.md`, log reasoning to `logs/SESSIONS.md`, reset `attempt` to 1 and `max_attempts` to 2 |
| 3 | **ESCALATE** |

**Never fix a failure by changing the test.**

### REPLAN
Re-read the relevant `docs/` sections and this step's entries in
`logs/ERRORS.md`. Write a new plan that explains **why the previous one failed**.
Log the architectural reasoning to `logs/SESSIONS.md`.

### ESCALATE
Append to `BLOCKED.md`:

- step, what was tried, all three failure modes
- best diagnosis
- **the specific decision or information needed from the user**

`git reset` the step's changes so the tree stays green. Add the step to
`steps_blocked`. Return to SELECT.

**A blocked step never blocks the run.** Continue with anything independent.

### COMMIT
- `git commit` naming the step and the requirement IDs closed
- Tick those boxes in `REQUIREMENTS.md`
- Rewrite `CONTEXT.md`
- Update `STATE.json`
- Architectural deviations only → `logs/SESSIONS.md`, **patching the contradicted
  doc in the same commit**

Return to SELECT.

---

## Exit conditions

Halt and write a final report to `BLOCKED.md`:

| | Condition |
|---|---|
| ✓ | Every `REQUIREMENTS.md` box ticked with a passing verify |
| ✗ | `.workflow/STOP` exists |
| ✗ | All remaining steps in `steps_blocked` |
| ✗ | Any `BUDGET.json` cap exceeded |
| ✗ | Same error signature 3× across different steps — systemic, stop burning money |
| ✗ | Full suite red for 3 consecutive commits |

**Final report:** what shipped, what didn't, what decisions are needed — in
priority order.

---

## Safety rails

**Git is the undo.** Commit before each step; ESCALATE resets. Never leave a
broken tree — the next step inherits it. Never `push`, force-push, rewrite
history, or delete a branch.

**Budget is a wrapper, not a ledger.** Every Anthropic call passes through one
function that checks the cap *before* calling and raises `BudgetExceeded`.
Appending cost after the fact caps nothing. Caps in `ARCHITECTURE.md` §6.

**Rate limits are enforced in code.** One shared limiter, 1 req/sec/domain,
honest User-Agent, `robots.txt` respected. An unattended retry loop that forgets
politeness is how you get IP-banned overnight — and a ban is not recoverable by
fixing code.

**Log rotation.** `logs/ERRORS.md` grows fast in a loop. Newest first, one-line
index at top. Past ~200 entries, consolidate resolved-and-never-recurred items
into a summary. An unread error log is worse than none — it creates false
confidence that the memory exists.

---

## Honest caveat

**The loop is the part everyone wants and the part that adds least.** Most of the
value here is in the `verify:` commands and the fixtures — those make review fast
and reliable whether or not anything runs unattended. The loop just spends tokens
while you sleep.

**Build the oracle first. Run it supervised. Only then take your hands off.**
