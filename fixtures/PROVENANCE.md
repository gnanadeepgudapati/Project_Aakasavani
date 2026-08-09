# Fixture provenance

`plans/00-implementation-plan.md` §5: every fixture is one of three kinds.
Re-record CAPTURED fixtures with `scripts/record_fixtures.py` when a feed or
API changes shape. Re-derive DERIVED fixtures from the captured file they're
based on. Re-author HAND-AUTHORED fixtures by hand, from the documented shape
of the real thing — never by "fixing" them to make a test pass.

All captures scrubbed of nothing (no cookies/auth headers were present in any
of these — they're all public, unauthenticated GET responses).

## Captured — real response, saved verbatim

| File | Source | Captured | Notes |
|---|---|---|---|
| `feeds/with_content_encoded.xml` | `feeds.feedburner.com/ndtvnews-top-stories` | 2026-08-09 | Real feed, trimmed to first 5 `<item>` blocks (was 20). `audit_feeds.py` confirmed `has_full_text=true` for this feed the same session |
| `feeds/without_content_encoded.xml` | `techcrunch.com/feed/` | 2026-08-09 | Same trim. `audit_feeds.py` confirmed `has_full_text=false` |
| `robots/permissive.txt` | `simonwillison.net/robots.txt` | 2026-08-09 | Untouched |
| `wayback/available_hit.json` | `archive.org/wayback/available?url=<a Wikipedia URL>` | 2026-08-09 | Chosen because Wikipedia pages have deep, reliable archive history — a smaller/newer site risked flapping between hit/miss on re-capture |

## Derived — real response, minimally mutated to create the pathology

| File | Derived from | How |
|---|---|---|
| `feeds/malformed.xml` | `with_content_encoded.xml` | Truncated 300 bytes into the first `<item>` — no closing tags at all. `feedparser` must set `bozo=1` and return without crashing, not raise |
| `feeds/empty.xml` | `with_content_encoded.xml` | All `<item>` blocks removed, channel wrapper and namespaces kept intact. Must parse with `bozo=False`, zero entries |

## Hand-authored — written from the documented shape of the real thing

These genuinely can't be captured on demand: you can't ask a site to 403 you,
a paywall stub depends on geography/cookie state, and GDELT rate-limited the
one live capture attempt (see below).

| File | Modeled on | Why it can't be captured |
|---|---|---|
| `articles/normal.html` | Ordinary long-form news article structure | Not pathological — hand-written for a clean, predictable extraction baseline rather than pinned to one outlet's exact (and mutable) HTML |
| `articles/paywall_stub.html` | A metered-paywall teaser pattern (short excerpt + subscribe CTA), `<500 chars` of real content | Paywall behavior is geography/cookie/session-dependent — not reliably reproducible by fetching from here |
| `articles/consent_wall.html` | A GDPR/cookie-consent interstitial, EU-targeted sites | Only shown to EU-geolocated or cookie-less requests |
| `articles/js_shell.html` | An SPA that server-renders nothing (empty `<div id="root">`, bundle `<script>`) | Depends on the target's build, not something to pin a fixture to |
| `articles/cloudflare_403.html` | Cloudflare's standard "Sorry, you have been blocked" challenge page | Triggering a real block on purpose means adversarial probing, which Rule 8 forbids outright |
| `gdelt/artlist.json` | `SOURCES.md` §2's documented DOC 2.0 `mode=artlist` response fields (`url`, `title`, `seendate`, `socialimage`, `domain`, `language`, `sourcecountry`) | **Attempted a real capture first** — `scripts/record_fixtures.py`, 2026-08-09 — and got `HTTP 429` even on a single request at 1 req/sec, with the same result on a retry after backoff. Hand-authored rather than retried further, per Rule 8: no aggressive retry against a rate limit |
| `gdelt/empty.json` | Same endpoint, zero-result case (`{"articles": []}`) | Trivial shape, not worth a live capture attempt |
| `wayback/available_miss.json` | The real "no snapshot" shape, observed directly during capture (`archive.org/wayback/available?url=simonwillison.net&timestamp=20260101` returned `{"archived_snapshots": {}}` before a Wikipedia URL was tried instead for the hit fixture) | The miss shape was *observed* live, just not the one kept as the canonical "hit" — recorded by hand from that real observation rather than a second capture |
| `robots/restrictive.txt` | Standard `Disallow: /` shape | Trivial, not worth a live capture — real restrictive robots.txt files vary only in cosmetic detail |
