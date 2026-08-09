# 06 — Feed parser + dedupe

`ARCHITECTURE.md` §8 step 06, §2.1-§2.3.

## Files

| File | Purpose |
|---|---|
| `app/ingest/canonical.py` | `canonicalize()`, `url_hash()`. Lowercases host only (not path — paths are case-sensitive on real servers), strips `utm_*`/`fbclid`/`gclid`/`mc_*`, drops fragment and trailing slash. **Deliberately does not resolve Google News redirects** — no frozen feed uses Google News (S-002), so that resolver would be dead code (plan risk R-12) |
| `app/ingest/parser.py` | `parse_feed()`, `resolve_description()` — the 5-tier fallback chain from `ARCHITECTURE.md` §2.3. Tiers 2-3 (og:/twitter:description) use a small regex rather than adding `beautifulsoup4` as an undeclared dependency, since it's one fallback tier extracting one meta-tag attribute |
| `app/ingest/dedupe.py` | `insert_if_new()` — URL-level dedup only, per Rule 2 |
| `tests/test_parser.py` | R-042…R-049 |

## What actually happened

One test bug, caught immediately: `test_canonicalise_strips_tracking`
asserted the canonicalized path would be lowercased
(`https://example.test/article`), but `ARCHITECTURE.md` §2.2 only specifies
lowercasing the **host**. Path case matters on real servers — lowercasing it
would silently break real URLs. Fixed the assertion to match the spec, not
the code.

**Retroactively closed 2 more rule tests** written at step 03:
`test_stored_description_is_verbatim` (R-002, D-1 — needed only
`resolve_description`'s verbatim-from-parser behavior) and
`test_six_outlets_six_entries` (R-004 — needed only `canonicalize`/`url_hash`/
`insert_if_new`).

## Acceptance criteria — closed

- [x] R-042…R-049 (`tests/test_parser.py`, all 8)
- [x] R-002, R-004 (retroactive, `tests/test_rules.py`)

## Which docs this implements

`ARCHITECTURE.md` §2.1 (ingest worker's parse step — minus the deleted D-4
15-min poller, this is invoked from the build/top-up jobs instead), §2.2
(dedupe), §2.3 (description fallback chain), §12.1 Rules 1 and 2.

## Requirement IDs closed

R-002, R-004, R-042, R-043, R-044, R-045, R-046, R-047, R-048, R-049.
