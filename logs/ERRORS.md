# ERRORS

**Check here BEFORE debugging anything.** An error you have already solved once
should never cost a second investigation.

Newest first. One-line index at the top. Past ~200 entries, consolidate
resolved-and-never-recurred items into a summary — an unread error log is worse
than none, because it creates false confidence that the memory exists.

---

## Index

*(empty — no errors yet)*

| ID | Signature | Step | Status |
|---|---|---|---|
| — | — | — | — |

---

## Entries

*(none yet)*

---

## Entry format

Copy this. Do not improvise a shape — the index depends on it.

```markdown
### E-001 · <ExceptionType>:<file>:<line>

**Step:** 06-feed-parser
**Attempt:** 2 of 3
**Date:** 2026-08-09

**Error — verbatim, not paraphrased:**

    Traceback (most recent call last):
      File "app/parser.py", line 44, in extract
        return entry.content[0].value
    AttributeError: 'FeedParserDict' object has no attribute 'content'

**Diagnosis:** feedparser omits `.content` entirely when a feed ships no
`<content:encoded>`, rather than returning an empty list.

**Tried:**
1. `entry.get('content')` — still raised, `.get` is not on the attr path
2. `getattr(entry, 'content', None)` — worked

**Fix:** `app/parser.py:44` — use `getattr` with a default, not attribute access.

**Prevention:** fixture `without_content_encoded.xml` now covers this path.
```

**Error signature** = `<ExceptionType>:<file>:<line of the top frame in our own
code>`. Not the top frame overall — a line inside `site-packages` is useless as a
signature. Three occurrences of one signature across *different* steps means
something systemic is wrong and the loop must EXIT.
