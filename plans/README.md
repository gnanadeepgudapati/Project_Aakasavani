# plans/

One plan per build step, named `NN-<step>.md`, **written before any code**.

Step numbers and names come from `ARCHITECTURE.md` §8 — the single authoritative
build order. Do not invent a second one here.

Every plan states, before implementation begins:

- **exact files** to create or modify
- **acceptance criteria, named as the tests that will exist** — not prose
- **which `REQUIREMENTS.md` IDs** it closes
- **which `docs/` sections** it implements

A plan that names no test is not a plan. If a step is re-planned after a failed
attempt, the new plan must explain **why the previous one failed** — see
`AUTONOMOUS-LOOP.md` § REPLAN.

Empty so far. `01-feed-audit.md` is next, once `BLOCKED.md` B-001 is resolved.
