# 26 — First real run + triage

`plans/00b-real-data-and-ui-plan.md` Track A step 26. The point of this step
is specifically to find what fixtures could not predict — `CLAUDE.md`'s
working style: "Test the ugly paths... these are the normal case, not the
exception."

## Procedure

1. `pytest tests/test_live.py --noconftest -v` — the manual canary. One real
   feed, one real article, before committing to the full 35.
2. `python scripts/run_build.py --db <scratch db>` against the real,
   frozen 35 feeds. Watch stdout. Rule 8 in full effect — no shortcuts for
   being a one-off run.
3. Inspect the result: `editions`/`edition_items` row counts,
   `seen.full_text` populated for front-page items, per-feed `fail_count`/
   `enabled` state.
4. Fix what breaks, in owned files only. Anything requiring a fixture/test
   change outside the allowed red-first workflow, or touching a forbidden
   file, is a `BLOCKED.md`-shaped finding to report, not a silent workaround.
5. Record honestly what the fixtures missed.

## Acceptance criteria

- R-107 a real run of `scripts/run_build.py` against the 35 real frozen feeds produces a `live` edition with `seen.full_text` populated for front-page items
- R-108 dead/blocked feeds (7 known from `BLOCKED.md` B-004, possibly more on the day of the run) fail gracefully — `fail_count` increments, the build still completes and swaps in a live edition, no exception escapes `run_build`
- R-109, R-110 — reserved for regression tests covering whatever the real run's fixtures-didn't-predict findings turn out to be

## What actually happened

### The run

1. `pytest tests/test_live.py --noconftest -v` — **passed** against the real
   internet on the first attempt.
2. `python scripts/run_build.py --db ./aakasavani.db` (redirected to a log
   file) — **succeeded**: 39 articles, edition `live`, `read_minutes=180`.
   Re-run twice more (once unredirected, once redirected) to check
   reproducibility and conditional-GET behaviour across polls — both
   succeeded identically in shape.
3. First invocation, run **directly to the console (not redirected)**,
   exited 1 with **zero captured output** — no traceback, nothing. Not
   reproduced on two subsequent identical invocations (one redirected, one
   not). Root cause undetermined — a `sys.stdout.encoding` check on this
   console reports `cp1252`, and printing an em dash directly to it
   (`"The Hindu — national"`) does not raise (Windows' console write path
   handles it), so this wasn't the classic Windows-console Unicode crash
   the environment notes warned about. Recorded here rather than
   hand-waved away: **real cron invocations always redirect stdout to a
   log file** (the only shape that matters operationally, and the only
   one that reproduced cleanly three times), so this is not blocking, but
   it is an honest unexplained data point, not a claimed fix.

### Verified: a real edition landed

```
editions:        1 row, status='live', article_count=39, read_minutes=180
edition_items:   39 rows (13 tech / 13 finance / 13 world_india)
seen:            1933 rows total, 60 distinct sources
front page:      39/39 have full_text or a recorded failure reason
                 33/39 full_text populated (32 'live', 1 'wayback')
                 35/39 image_url populated (og:image fills real gaps)
```

### D-1..D-8, proven against reality, not just fixtures

- **D-1** (registry sync): `sync_feeds_to_db` populated all 35 real feeds
  from `data/feeds.yaml` into a brand-new DB on first run.
- **D-2/D-5** (poll hardening): 5 feeds failed every single real poll
  (`Business Standard`, `PIB`, `AP`, `Anthropic news`, `Moneycontrol`) —
  confirmed by hand with a direct `_default_feed_fetch` call: still
  `403`/`403`/`404`/`404`/`403` respectively, **exactly** matching
  `BLOCKED.md` B-004's original step-01 audit findings. `fail_count`
  climbed 1→2→3 across three runs; the other 30 feeds stayed at 0. The
  build completed and swapped in a live edition every time regardless.
- **D-3/D-4** (conditional GET + shared limiter): real `ETag`/
  `Last-Modified` values were stored for the feeds that send them (Times
  of India, Indian Express, Economic Times, Al Jazeera, Guardian,
  TechCrunch, The Verge, Hacker News, Lobsters, Hugging Face,
  MarketWatch — 11/35 send at least one of the two); the rest legitimately
  send neither (nothing to store — not a bug).
- **D-6** (robots wiring): confirmed with real robots.txt files, not test
  fixtures — `lobste.rs/s/...` and `marketwatch.com/story/...` both came
  back `reason="robots_disallow"` from `default_fetcher()` on the real
  build path, i.e. the production wiring (not a hand-built `Fetcher`)
  actually consulted and honoured real robots.txt files.
- **D-7** (`og:image`): 35/39 front-page items got an image; of the 4
  without, 3 never got any `page_html` at all (robots-blocked or total
  extraction failure — nothing to extract an image from), and the 4th
  (`nickvsnetworking.com`) was checked by hand — the live page genuinely
  has no `og:image`/`twitter:image` meta tag at all. Zero false negatives
  found.
- **D-8** (`read_minutes`): `180` on a real edition, consistent with 33
  articles of real prose ÷ 220 wpm.

### What the fixtures had missed — real findings

1. **A feed can return real HTTP 200 with genuinely malformed XML, and
   this is currently indistinguishable from "successful, zero new items"
   for `fail_count` purposes.** `The Print` and `Scroll.in` (also in
   `BLOCKED.md` B-004, originally recorded as `no_entries (bozo)`) both
   returned 200 with substantial bodies (997 KB / 114 KB) on every real
   poll — not blocked, not down — but `feedparser` reports `bozo=1` with
   **zero parseable entries** both times (confirmed by hand:
   `<unknown>:2:0: syntax error` and `<unknown>:38:71: not well-formed
   (invalid token)`). `parse_feed`'s own contract (R-044) is to never
   raise on malformed XML, so `poll_all_feeds`'s per-feed `try/except`
   never sees an exception — this is legitimately a *successful* poll by
   the letter of D-2/D-5 as specified, but it means a feed that is
   permanently broken this way is **never auto-disabled**, unlike a
   403/404 feed. `ARCHITECTURE.md` §5's failure table only names "404 /
   timeout", not "200 with unparseable content". This is exactly the
   category the task brief predicted ("feeds returning 200-with-garbage")
   — **not silently fixed**, since deciding whether a persistent
   zero-entry parse should count toward `fail_count` is a spec decision
   outside D-1..D-8's scope, and changing it would mean re-litigating
   `ARCHITECTURE.md` §5, which this task does not own. Locked in as
   current, intentional behaviour with a new regression test
   (`test_200_with_unparseable_xml_is_not_counted_as_a_failure`, R-109),
   and flagged here for a real decision.
2. **A "suspicious" em-dash/apostrophe rendering was a diagnostic-script
   artifact, not a data bug.** Spot-checking real titles by printing them
   directly to this Windows console (cp1252) showed replacement
   characters (`�`) in place of em dashes and curly apostrophes. Checked
   by writing the same row to a UTF-8 file instead: the stored value was
   the correct Unicode codepoint (`’` U+2019) throughout — SQLite/
   feedparser/`parse_feed` handle real-world Unicode correctly; only
   *my own ad-hoc print-to-console diagnostics* needed
   `PYTHONIOENCODING=utf-8`, exactly as this task's own environment notes
   warned. No code change; recorded so this doesn't get mistaken for a
   real encoding bug later.
3. **Al Jazeera's "all.xml" feed mixes video pages into the article
   stream.** Two front-page items were Al Jazeera `/video/...` URLs with
   real, substantial `<description>` text (so they passed selection
   normally) but essentially no extractable article body — Trafilatura
   correctly returned under the 500-char floor and the fetch fell through
   exactly per `ARCHITECTURE.md` §2.4's "headline + description + link
   only" honest floor. No fixture had a video-page HTML sample, so this
   exact shape of extraction failure was never exercised before this run
   — but the SYSTEM behaved correctly, no code change needed.
4. **Redirected vs. non-redirected stdout on Windows is not guaranteed
   equivalent** — see the unexplained exit-1 above. Not fixed (not
   reproduced), but worth remembering for anyone debugging a future cron
   failure that "looked fine when I ran it by hand."

None of D-1..D-8 broke under real load. The one real gap found (finding
#1) is a genuine, previously-undocumented edge case in `ARCHITECTURE.md`
§5's failure taxonomy, reported rather than silently decided.
