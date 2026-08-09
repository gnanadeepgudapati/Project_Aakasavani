# 27 — UI completion (Track B, `plans/00b-real-data-and-ui-plan.md` §3)

Closes gaps G-1…G-4: four Phase-1 features named in `ROADMAP.md` with working,
tested backends but **no route or template that a human can reach**. This
plan wires the existing backends to the page. It does not touch Track A
(the data pipeline), which another agent builds concurrently in a separate
worktree.

**Requirement ID range: R-111…R-130.** Not all IDs are used; IDs are not
renumbered to close gaps, per `REQUIREMENTS.md`'s own rule.

---

## Files touched (all inside this agent's ownership list)

| File | Change |
|---|---|
| `app/migrations/004_seed_topics.sql` | **NEW.** Seeds the 4 topics from `EDITION-AND-UI.md` §2.2 |
| `app/web/routes.py` | `topic` query param on `/` and `/edition/{date}`; `POST /topics`; `GET /search` |
| `app/web/research_routes.py` | Timeline route wrapped to degrade gracefully instead of a raw 500 |
| `app/topics.py`, `app/search.py` | Minor defensive fix (empty search query) |
| `app/web/templates/base.html` | Header gets a search box + density toggle, present on every page |
| `app/web/templates/index.html` | Topic chip row, `+ new` form, topic-filtered rendering |
| `app/web/templates/_row_hero.html` | `onerror` handling added (missing before — thumb had it, hero didn't) |
| `app/web/templates/article.html` | Research side panel markup (Ask/Timeline/Explain tabs) |
| `app/web/templates/search.html` | **NEW** |
| `app/web/static/app.css` | Panel layout, density-mode rules, chip/form styling |
| `app/web/static/app.js` | Density persistence, chip-selection persistence, panel open/close/resize/tabs, Ask/Timeline/Explain wiring |
| `tests/test_feed_view.py`, `tests/test_topics.py`, `tests/test_search.py`, `tests/test_article_view.py`, `tests/test_panel.py` | New acceptance tests |
| `tests/test_ui.py` | **NEW** — static checks for client-side-only behaviour (density CSS, panel-width persistence key, explain-selection-only) that can't be expressed as a normal HTTP assertion without a browser |

---

## G-1 · Research side panel

`EDITION-AND-UI.md` Part 3. Four endpoints already exist in
`app/web/research_routes.py` and are untouched in behaviour except one fix
(below). `article.html` gets:

- A right-docked `<aside id="research-panel">`, closed by default
  (`aria-hidden="true"`, zero width). A `#research-open` button toggles a
  `panel-open` class on a wrapping `.article-layout` flex container, which is
  what actually does the 60/40 reflow in CSS — the panel and the article are
  siblings, not stacked.
- Three tabs (`Ask` / `Timeline` / `Explain`) implemented as plain buttons
  toggling `hidden` on sibling panels — no framework, per `CLAUDE.md`'s
  vanilla-JS stack line.
- **Ask**: "Summarise this article" button (sends the fixed question
  `"Summarise this article."` through the same `/ask` endpoint — no separate
  summarise endpoint exists, and none is needed), the lazily-fetched starter
  questions as clickable buttons, and a free-text form.
- **Timeline**: fetches `/research/{hash}/timeline?query=<article title>` the
  first time the tab is opened, renders the metadata list.
- **Explain**: reads `window.getSelection()` at click time and sends only
  that string — never the article's `full_text` — to `/explain`.
- **Resizable**: a drag handle on the panel's left edge; width written to
  `localStorage["aakasavani:panel-width"]` on `mouseup`, re-applied on open.
- **Lazy loading, never at page load**: starter questions fetch only inside
  `openPanel()`, which only runs from the open button's `click` handler.
  Nothing on `/article/{hash}`'s server-rendered response touches
  `app.research.*` — `app/web/routes.py` still imports nothing from it, so
  `tests/test_rules.py::test_no_llm_import_in_render_path` (R-001, untouched)
  keeps proving this statically. New tests below prove it dynamically too.

### Two real bugs found (not hypothetical) — both fixed at the route boundary

**1. Timeline.** `app/research/timeline.py`'s real `_default_wikipedia`/
`_default_gdelt`/`_default_guardian` all currently `raise
NotImplementedError("not wired until deployment")` — that file is owned by
the other track and out of scope here. Called unmocked (i.e. once a human
actually opens the Timeline tab with no fixture injected), `get_timeline()`
propagates that exception straight through `research_routes.py`'s
`timeline()` handler, which FastAPI turns into a raw 500.

**2. Ask / Explain / starter-questions, with no `ANTHROPIC_API_KEY` at
all** (`BLOCKED.md` B-002 — the actual current state of this deployment,
not a hypothetical). `app/research/budget.py::budgeted_call` only wraps
`check_before_calling()` in `try/except BudgetExceeded` — the `fn()` call
itself (line `text, actual_usd_cost = fn()`) is unguarded. With no API key
configured, the Anthropic SDK fails *locally* at header/credential
validation (`anthropic._client.Anthropic._validate_headers` raises
`TypeError("Could not resolve authentication method...")`) **before
attempting any connection at all** — confirmed by hand against the running
dev server, not assumed. That `TypeError` propagated straight through
`research_routes.py` as a raw 500 for all three endpoints. This is exactly
the scenario the brief names directly: "There is currently no
`ANTHROPIC_API_KEY`... The panel must show a clean, honest state."

Both fixes live at the route boundary since `app/research/*` is out of
ownership here. Each of the four routes now returns `{"entries": [],
"error": ...}` or `{"error": ...}` on failure — the same shape
`budgeted_call`'s `BudgetedResult` already uses for a budget breach, so the
client JS's `if (data.error)` handling covers all four failure modes
uniformly.

**The ask/explain/starter-questions fix had to be scoped carefully.**
`tests/test_rules.py::test_no_network_on_reading_path` (R-010, not owned or
editable here) proves `/research/*` genuinely reaches the network by
setting a *syntactically-valid but fake* `ANTHROPIC_API_KEY`, which gets
the SDK past local header validation so it attempts a real connection —
which the test's network guard intercepts, and the resulting
`NetworkAccessError` (wrapped by the SDK's own `APIConnectionError`) must
still propagate out of the route call for that test to mean anything. A
blanket `except Exception: return {"error": ...}` around `budgeted_call`
would silently swallow that too, breaking R-010's proof without technically
touching its file. The fix instead walks `__cause__`/`__context__` (the
same technique R-010's own test uses) looking for `NetworkAccessError` by
class name, and re-raises if found — only a *local*, pre-network failure
(the missing-API-key case) gets converted to a graceful response.
`test_network_guard_failure_still_propagates` in `tests/test_panel.py`
reproduces R-010's exact scenario against `/ask` as the guard-rail for this
distinction, and the full `test_rules.py` suite (20 tests, unmodified)
stays green throughout.

## G-2 · Topic chips

- `app/migrations/004_seed_topics.sql` inserts the 4 topics verbatim from
  `EDITION-AND-UI.md` §2.2 (Energy, AI, Geopolitics, Crypto).
- `front_page()` and `edition_by_date()` gain a `topic: str | None` query
  param. `_render_edition()` now branches: if `topic` is set, it calls
  `app.topics.match_topic()` (matches **all** unexpired `seen` rows, not
  just today's edition front page — that's the whole point of a saved query
  being retroactive) instead of `_edition_sections()`, groups the results by
  `section` into the same `{section: [rows]}` shape `_edition_sections()`
  already produces, and reuses the *same* `index.html` per-section loop —
  no template branching needed for the list itself. `section` and `topic`
  compose (`?section=tech&topic=AI` narrows to both), satisfying
  `EDITION-AND-UI.md` §2.3's "combinable."
- `+ new` is a `<details>`-disclosed form POSTing `name`+`query` to a new
  `POST /topics`, which calls the existing `add_topic()` and redirects to
  `/` (303). A duplicate name (`topics.name` is `UNIQUE`) is caught and
  turned into a 400, not a raw `IntegrityError` 500.
- Selection persists via `localStorage` (`aakasavani:section` /
  `aakasavani:topic`), restored client-side only when a bare `/` is visited
  with no query string at all — an explicit link with `?section=` always
  wins, so a chip click is never silently overridden by a stale stored
  value.

**Naming collision found and resolved:** `tests/test_topics.py`'s existing
`test_topic_query_matches` and `test_topic_editable` call `add_topic(conn,
"AI", ...)` and `add_topic(conn, "Geopolitics", ...)` respectively —
`db_conn` runs every migration including the new 004, so those two names
now already exist by the time those tests run, and `topics.name UNIQUE`
turns the test's own `add_topic()` call into an `IntegrityError`. Renamed
the two colliding test fixture names only (`"AI"` → `"AI Beat"`,
`"Geopolitics"` → `"World Affairs"`); no assertion or test intent changed,
only the arbitrary string used as a fresh topic name in a test that isn't
actually about the seeded topics. This is not "weakening a test" — the
seed data is new and genuinely collides with an incidental literal; the doc
names Energy/AI/Geopolitics/Crypto are fixed by `EDITION-AND-UI.md` §2.2 so
the migration keeps them, and the test's own throwaway name moves instead.

## G-3 · Search page

`GET /search?q=` renders `app/search.py::search_read()` results in a new
`search.html`. Empty/blank `q` renders the page with no results and no
error (was previously going to hit FTS5 with an empty `MATCH` string and
raise `OperationalError` — guarded both in the route and defensively inside
`search_read()` itself). `search_read()` already scopes to `read`/`read_fts`
only (R-088, untouched) — new tests assert the same boundary holds through
the HTTP route, not just the function.

## G-4 · Density toggle

Three `localStorage`-persisted modes (`compact` / `comfortable` / `visual`),
applied as `data-density` on `<body>`, driving CSS only — no server
round-trip, no template branching:

- **Compact**: `display:none` on every `.hero-image`/`.thumb-image`.
- **Comfortable** (default, no attribute needed): unchanged existing rules.
- **Visual**: overrides `.row.thumb` to stack like `.row.hero` (full-width
  image, bottom mask-fade) instead of the 90×62 side thumbnail — reuses the
  *same* `<img>` element and URL already in the DOM; no new markup, no
  extra request.

Buttons live in `base.html`'s header so the control is present everywhere,
matching the header's existing sticky-nav treatment.

## Design decisions / ambiguities resolved

1. **Where does topic filtering search?** `EDITION-AND-UI.md` §2.2 says a
   new topic is "retroactive... matches the whole history," which only
   makes sense if the topic view queries all of `seen`, not just the ~39
   front-page items. Went with that reading rather than restricting topic
   filtering to today's edition, which would have silently contradicted the
   doc's own stated selling point for the feature.
2. **Summarise button** — no dedicated summarise endpoint exists in
   `app/web/research_routes.py` and none is named in
   `plans/00-implementation-plan.md`'s step list (15–17 are Ask/Timeline/
   Explain only). Implemented as a canned question through the existing
   `/ask` endpoint rather than inventing a new route, since `ask_question()`
   already accepts arbitrary free text and grounds/cites identically.
3. **Timeline query string** — the endpoint takes a bare `query` param with
   no specified source. Used the article's own `<h1>` title text, read
   client-side at tab-open time — the only per-article search term already
   on the page with no extra request.

## Requirement IDs closed

R-111…R-130, all used. See the final report for the full ID → `verify:`
mapping.
