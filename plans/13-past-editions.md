# 13 — Past editions

`ARCHITECTURE.md` §8 step 13, §6 ("Past editions: browsable by date"). The
routes (`/edition/{date}`) already existed from step 08 — this step is
primarily the dedicated acceptance tests, which caught a real bug the step
08 tests hadn't exercised.

## A real bug found: remainder leaked across edition dates

`test_edition_by_date` failed first for a genuine reason: browsing
`/edition/2026-08-08` showed an article from the **2026-08-09** edition in
its "show everything" remainder section — an article that, on the 8th,
hadn't been published yet. `_remainder()` queried the current, undated
firehose (`seen` minus today's `edition_items`) regardless of which
historical edition was being viewed.

**Fixed:** `_render_edition()` now only computes `remainder` when the
edition being rendered is the **live** one (`edition["status"] == "live"`).
A past (superseded) edition shows exactly what was on its front page and
nothing else — "show everything" is a live-edition concept, not something
that makes sense retroactively. `app/web/routes.py`.

## Two test bugs, also found and fixed

- `test_edition_by_date` and `test_root_serves_latest_live` initially used
  possessive titles ("Today's Lead"); Jinja2 correctly HTML-escapes `'` as
  `&#39;`, so a literal-string `in resp.text` check failed against otherwise
  correct output. Fixed by removing apostrophes from test fixture titles.
- `test_root_serves_latest_live` originally asserted the superseded
  edition's article was **absent** from `/` entirely — but it legitimately
  still belongs in the *live* edition's own "show everything" remainder
  (unexpired firehose content that didn't make today's front page is not
  the same claim as "belongs to yesterday's edition"). Rewrote the
  assertion to check front-page placement specifically (before the
  `remainder` marker in the HTML), which is what R-074 actually claims.

## Acceptance criteria — closed

- [x] R-072 `test_past_editions.py::test_edition_by_date`
- [x] R-073 `test_past_editions.py::test_unknown_date_404`
- [x] R-074 `test_past_editions.py::test_root_serves_latest_live`

## Which docs this implements

`ARCHITECTURE.md` §6 ("Past editions: browsable by date").

## Requirement IDs closed

R-072, R-073, R-074.
