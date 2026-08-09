# 03 — `tests/test_rules.py`

`ARCHITECTURE.md` §12.1. The oracle, part 2 — and the one step whose own
build order is genuinely unusual, so this plan explains the design before
the acceptance criteria.

## The core design problem

Most rule tests exercise app modules that don't exist until much later steps
(schema=04, extraction=05, edition build=07, web=08-09, panel=15-17). But
`ARCHITECTURE.md` §8 is explicit: this file "must be red before any feature
exists, green after," and it "runs on every verify, for every step, forever"
— meaning steps 04 through 21 all re-run this exact file as part of their own
verify chain. If the file failed to *collect* because of a hard top-level
`import app.web.routes` (step 08) three steps early, every step from 04
through 07 would fail their own verify chain forever, on a module that isn't
even due to exist yet.

**Fix: every test does its own import, inside the function body, never at
module top level.** A test whose target doesn't exist yet fails only itself,
cleanly, for the right reason ("module not found" — a legitimate "red because
the feature isn't built"), and every other test in the file still collects
and runs normally.

## The second design problem — "prove it catches a violation," against code
## that doesn't exist yet

Prompt 2 requires each rule test be shown catching a real violation before it
counts. For a test that needs `app.edition.build` (step 07), there is nothing
to break yet. Three different answers, depending on the test:

1. **Static-analysis tests (R-001, R-007)** — the mechanism (walk the import
   graph, look for `anthropic`) can be proven correct *independently* of
   whether `app.web.routes`/`app.edition.build` exist, by running it against
   a synthetic package built inside the test. `tests/_static_analysis.py` +
   `test_static_analysis_helper_catches_a_real_case` do exactly this — and it
   found a real bug: the relative-import resolver (`from . import X`)
   mis-resolved the base package, silently breaking transitive-import
   detection. Fixed and re-verified (`plans/00-implementation-plan.md`'s own
   design intent — a test that's never been red proves nothing — applied to
   the test infrastructure itself, not just app code).

2. **Fully self-contained tests (R-014, R-016, R-019)** — `app.config`
   already exists, and "which packages are installed" is true right now, not
   contingent on a future step. These were demonstrated for real: a
   Chrome-impersonating User-Agent string, a simulated `selenium` install,
   and a simulated `redis`+`sqlalchemy` install were each fed through the
   real check logic and confirmed caught, then the real (clean) values were
   confirmed to pass. Ticked in `REQUIREMENTS.md` now.

3. **Everything else (14 tests)** — genuinely cannot be violation-tested
   before their dependent step exists. Written now, correct by inspection and
   by design review, left unticked. **A final pass, after the last build step
   (19), re-runs every one of the 19 Ten-Rules tests, and for each: breaks
   the real (now-finished) implementation in the specific way the rule
   guards against, confirms red, restores, confirms green again.** That
   final pass is more rigorous than doing it now against throwaway stubs
   would have been — it exercises the actual shipped code, not a stand-in.

## Files

| File | Purpose |
|---|---|
| `tests/_static_analysis.py` | Import-graph walker: `imports_reachable_from(module, root)`. Parses AST, never executes the target code |
| `tests/test_rules.py` | All 19 Ten-Rules tests |

## Acceptance criteria

- [x] R-001, R-007 — static, vacuously true until steps 08/07, mechanism proven
- [x] R-014, R-016, R-019 — self-contained, genuinely demonstrated today
- [ ] R-002…R-006, R-008…R-013, R-015, R-017…R-018 — written, correct by
      design, close as their dependent step lands; final violation-proof at
      the end of the build

## Which docs this implements

`ARCHITECTURE.md` §12.1 (the rule→test mapping, including the D-1/D-2/D-3
amendments), §12.3 (red-first — applied here to the test infrastructure
itself, per item 1 above), §8 ("must be red before any feature exists, green
after" — the literal design constraint this plan's first section explains).

## Requirement IDs closed (this pass)

R-001, R-007, R-014, R-016, R-019. Remaining 14 close incrementally through
steps 04–19, formally re-verified in a final pass after step 19.
