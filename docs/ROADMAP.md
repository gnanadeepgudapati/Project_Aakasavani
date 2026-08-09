# Project Aakasavani — Roadmap

---

# Phase 1 — The morning edition

**Scope: a news reader. Nothing else.**

Built to `ARCHITECTURE.md` and `EDITION-AND-UI.md`:

- 04:00 IST edition build, pre-fetched, atomic swap
- Front page (~40 articles) + full ingest underneath
- Section chips (from per-section feeds) + topic chips (saved FTS queries)
- Article view — instant, whole, unaltered, images inline
- Research side panel — Ask / Timeline / Explain, AI on request only
- Hero + thumbnail images, density toggle
- SQLite: `seen` (TTL 30d) + `read` (permanent) + FTS5
- Internet Archive snapshot of every front-page article, overnight

**Cost: ~$10–16/month. No LLM anywhere except the panel, on request.**

**Ship steps 01–09 and live with it for two weeks before building anything
below.** (`ARCHITECTURE.md` §8: "Steps 01–09 are the product." Steps 1–5 alone
have no feed view and no article view — not a usable edition.)

---

# Phase 2 — The morning brief *(parked)*

## The idea

Extend from *"a news reader I open at 7am"* to *"the one page I open at 7am"* —
news, today's tasks, today's calendar, assembled together.

This is a coherent product shape, not a widget pile. The distinction matters and
is defended below.

## Why it fits this architecture cleanly

The 04:00 build job already runs before you wake and already performs an atomic
swap. It can pull calendar and tasks in the same pass and assemble the entire
morning as one unit. No new infrastructure:

| Needed | Already exists |
|---|---|
| Scheduled pre-dawn job | ✅ edition build |
| Atomic publish | ✅ `editions` staging + swap |
| Storage | ✅ SQLite, two more small tables |
| Web page | ✅ same page, one added strip |
| Failure handling | ✅ degrade to yesterday, never blank |

## The risk, stated now so it doesn't happen quietly

**Personal dashboards accrete widgets until nothing on the page is good.**

Weather, stocks, habit trackers, quote-of-the-day, RSS of RSS. Each addition is
individually reasonable and collectively fatal — the news becomes one panel among
eight, and the thing that was excellent becomes adequate.

**Guardrail: Phase 1 must remain the page. Phase 2 adds a narrow strip above the
edition, not a second product beside it.** If the tasks strip ever occupies more
vertical space than the front page's lead story, it has gone wrong.

## Likely shape

```
┌────────────────────────────────────────────────┐
│  Friday, 7 August 2026                         │
│  ─────────────────────────────────────────     │
│  TODAY   3 tasks · 2 meetings                  │  ← narrow strip
│   ○ Task one                     09:30 Standup │
│   ○ Task two                     14:00 Review  │
├────────────────────────────────────────────────┤
│  FRONT PAGE                          47 articles│  ← unchanged, still the page
│  …                                              │
└────────────────────────────────────────────────┘
```

## Open technical questions for Phase 2

**Calendar** — read-only is much simpler than read-write and probably enough.

| Option | Notes |
|---|---|
| Google Calendar API | Most likely. OAuth, read-only scope, well documented |
| `.ics` subscription URL | Simplest possible — poll a URL, parse with `icalendar`. No OAuth |
| CalDAV | Universal but fiddly |

The `.ics` route deserves serious consideration: most calendar products expose a
secret subscription URL, and polling it at 04:00 needs no auth flow at all.

**Tasks** — the real question is whether to own them or integrate.

| Option | Trade-off |
|---|---|
| **Own table in SQLite** | Full control, no dependency, but you must build task entry and it becomes another place tasks live |
| Todoist / Google Tasks / TickTick API | Tasks stay where you already manage them. Adds an integration and an auth flow |
| Apple Reminders | Poor API story on a Linux VPS |

**Recommendation when the time comes: integrate, don't own.** A second todo list
that isn't your real todo list is worse than none — it becomes stale within a week
and then actively misleads you.

## Explicitly out of scope for Phase 2

Recorded to keep the guardrail enforceable:

- ❌ Weather widget
- ❌ Portfolio / stock ticker strip
- ❌ Habit tracking
- ❌ Email inbox preview
- ❌ Notes
- ❌ Anything that makes the page taller than one screen before the news starts

---

# Phase 3 — Mobile *(unscheduled)*

Same backend, same API, different client. Deferred deliberately — the web page
must be genuinely good first, and layout decisions made under mobile constraints
tend to compromise the desktop reading experience.

Design work already done that carries over: side panel becomes a bottom sheet,
highlight-to-explain triggers on long-press, density toggle defaults to Compact.

---

# Deliberately never

From `ARCHITECTURE.md` §9, restated because these tend to return:

- ❌ AI summaries in the feed
- ❌ Cross-article synthesis or truth adjudication
- ❌ Multi-user support
- ❌ Public serving of stored article text
- ❌ Bot-detection evasion
