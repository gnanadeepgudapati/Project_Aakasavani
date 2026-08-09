# 10 — Topic chips

`ARCHITECTURE.md` §8 step 10, `EDITION-AND-UI.md` §2.2. First step past "the
product" (01–09) — an enhancement, per `ROADMAP.md`'s "ship and decide" gate.

## Files

| File | Purpose |
|---|---|
| `app/topics.py` | `add_topic()`, `update_topic_query()`, `set_topic_enabled()`, `list_topics()`, `match_topic()` |
| `tests/test_topics.py` | R-062…R-064 |

## What actually happened

Two of three tests passed immediately. `test_topic_editable` failed for a
real, worth-knowing reason: FTS5's default `unicode61` tokenizer does not
stem. A query for `tariff` does not match an article containing `tariffs` —
confirmed directly (`SELECT ... WHERE seen_fts MATCH 'tariff'` vs.
`'tariffs'` against the same row). Not a bug in `match_topic()`; the test
assumed stemming that was never part of R-064's actual requirement ("editable
at runtime," not "fuzzy matching"). Fixed the test to use the real word form,
and added a note to `EDITION-AND-UI.md` §2.2 so a real topic author doesn't
get burned by the same assumption — the doc's own example topics already
avoid the problem by spelling out multiple word forms (`renewable`, not just
`renewables`), which now reads as deliberate rather than coincidental.

## Acceptance criteria — closed

- [x] R-062 `test_topics.py::test_topic_query_matches`
- [x] R-063 `test_topics.py::test_new_topic_is_retroactive`
- [x] R-064 `test_topics.py::test_topic_editable`

## Which docs this implements

`EDITION-AND-UI.md` §2.2 (saved queries, the "why queries beat tags" table).

## Requirement IDs closed

R-062, R-063, R-064.
