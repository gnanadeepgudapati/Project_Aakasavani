# 99 — Final violation-demonstration pass

Promised in `plans/03-rules.md`: the 13 Ten-Rules tests that were written
correct-by-design at step 03 but couldn't be individually demonstrated until
their dependent modules existed. All 19 are done now. This is the record.

## Method

For each: break the real (finished) implementation in the specific way the
rule guards against → run only that test, confirm red **for the stated
reason** → restore the exact original code → confirm `git diff --stat` shows
no residual change. No test file was ever touched — every break lived in
`app/`, restored before moving to the next one.

## Results

| Rule | Test | Break introduced | Confirmed red because |
|---|---|---|---|
| 2 (storage verbatim) | R-002 | `resolve_description` uppercased the RSS description | stored text no longer matched feedparser's own output |
| 1 (render sanitiser) | R-003 | sanitiser reversed the string | word-order subsequence check failed |
| 2 (URL dedup) | R-004 | `canonicalize()` dropped the host entirely | 6 outlets' same-path URLs collapsed to 1 row |
| 3 (extractor purity) | R-005 | `extract_full_text` truncated to 50 chars | `len(text) > 500` failed |
| 4 (build never calls LLM) | R-006 | `run_build` constructed `anthropic.Anthropic()` | the test's own forbidden-call spy raised |
| 5 (sweep strips text) | R-008 | sweep's `UPDATE` dropped `full_text`/`fetched_via` from the SET clause | those columns stayed populated after sweep |
| 5 (read never expires) | R-009 | sweep added a stray `UPDATE read SET full_text = NULL...` | a `read` row lost its title/text |
| 7 (failed build keeps live) | R-011 | `run_build` optimistically superseded the old edition *before* selection could fail | no `live` edition existed at all after the failure |
| 7 (atomic swap) | R-012 | swap's `except` block dropped the `raise` | `pytest.raises(RuntimeError)` saw no exception |
| 8 (limiter enforced) | R-013 | `acquire()` always returned `0.0` regardless of the real wait computed | `waited >= 0.7` failed |
| 8 (robots respected) | R-015 | `is_allowed()` ignored the parser's answer, returned `True` always | a `Disallow: /` fixture was reported as allowed |
| 9 (dwell columns exist) | R-017 | removed `dwell_seconds` from the `read` migration | `PRAGMA table_info` no longer listed it |
| 9 (dwell written) | R-018 | `/article/*/close` accepted the payload but never wrote it | `read.dwell_seconds` stayed `NULL` after closing |

R-001, R-007 (static-analysis mechanism), R-010 (both the reading-path and
`/research/*` halves), R-014, R-016, R-019 were demonstrated earlier, at
steps 03/08/15 respectively — see those plans.

## Verification after the pass

```
git diff --stat        → empty (every break fully reverted)
python -c "import app" → OK
pytest                  → 92 passed
```

**All 19 `tests/test_rules.py` tests have now been shown, individually, to
catch the specific real violation they exist to guard against.** The oracle
`AUTONOMOUS-LOOP.md` describes — "something that answers 'is this done?'
without a human in the room" — is no longer just asserted to work. It's been
tested.
