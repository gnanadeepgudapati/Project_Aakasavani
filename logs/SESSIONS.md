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
