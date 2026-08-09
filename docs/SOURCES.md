# Sources

**REFERENCE — look things up here. Do not implement from this file alone;
`ARCHITECTURE.md` decides what is in scope.**

Only sources actually used in Phase 1 are listed. Alternatives that were
evaluated and rejected have been removed — that evaluation is settled.

---

## 1. RSS feeds — the backbone

> ### 🔒 FROZEN — this list is final for Phase 1
>
> Autonomous mode requires a fixed feed list. Do not add, remove, or substitute
> feeds during a build. If a feed is dead or malformed, mark
> `feeds.fail_count` and log to `BLOCKED.md` — do not silently swap in another.
> Changing this list is an architectural decision: `logs/SESSIONS.md`, and only
> outside an autonomous run.

**Subscribe to per-section feeds, not per-outlet.** The section is the category,
assigned by the publisher, free and accurate. Store it in `feeds.section`.

**Audit every feed for `<content:encoded>`.** Feeds carrying the full article body
never need fetching — no live request, no 403, no Wayback fallback. Record the
result in `feeds.has_full_text`. This is build step 1.

### India

| Outlet | Feed |
|---|---|
| The Hindu — national | `https://www.thehindu.com/news/national/feeder/default.rss` |
| The Hindu — business | `https://www.thehindu.com/business/feeder/default.rss` |
| The Hindu — sci-tech | `https://www.thehindu.com/sci-tech/feeder/default.rss` |
| Times of India — top | `https://timesofindia.indiatimes.com/rssfeedstopstories.cms` |
| Livemint — news | `https://www.livemint.com/rss/news` |
| Livemint — markets | `https://www.livemint.com/rss/markets` |
| Livemint — companies | `https://www.livemint.com/rss/companies` |
| NDTV — top | `https://feeds.feedburner.com/ndtvnews-top-stories` |
| NDTV — india | `https://feeds.feedburner.com/ndtvnews-india-news` |
| Hindustan Times — india | `https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml` |
| Indian Express — india | `https://indianexpress.com/section/india/feed/` |
| Business Standard | `https://www.business-standard.com/rss/home_page_top_stories.rss` |
| Economic Times | `https://economictimes.indiatimes.com/rssfeedstopstories.cms` |
| The Print | `https://theprint.in/feed/` |
| Scroll.in | `https://scroll.in/feed` |
| PIB (govt. releases) | `https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3` |

### World

| Outlet | Feed |
|---|---|
| AP — top | `https://apnews.com/hub/ap-top-news.rss` |
| BBC — world | `https://feeds.bbci.co.uk/news/world/rss.xml` |
| Al Jazeera | `https://www.aljazeera.com/xml/rss/all.xml` |
| Guardian — world | `https://www.theguardian.com/world/rss` |
| NYT — world | `https://rss.nytimes.com/services/xml/rss/nyt/World.xml` |
| NPR | `https://feeds.npr.org/1004/rss.xml` |
| DW | `https://rss.dw.com/rdf/rss-en-world` |

### Tech / AI / dev

| Outlet | Feed |
|---|---|
| TechCrunch | `https://techcrunch.com/feed/` |
| The Verge | `https://www.theverge.com/rss/index.xml` |
| Ars Technica | `https://feeds.arstechnica.com/arstechnica/index` |
| Hacker News (100+ pts) | `https://hnrss.org/newest?points=100` |
| Lobsters | `https://lobste.rs/rss` |
| Simon Willison | `https://simonwillison.net/atom/everything/` |
| Anthropic news | `https://www.anthropic.com/news/rss.xml` |
| Hugging Face blog | `https://huggingface.co/blog/feed.xml` |

### Finance

| Outlet | Feed |
|---|---|
| CNBC | `https://www.cnbc.com/id/100003114/device/rss/rss.html` |
| MarketWatch | `https://feeds.content.dowjones.io/public/rss/mw_topstories` |
| Moneycontrol | `https://www.moneycontrol.com/rss/latestnews.xml` |
| BBC — business | `https://feeds.bbci.co.uk/news/business/rss.xml` |

### Fallback for sources without feeds

**Google News RSS** — free, no key, arbitrary query, geo-targeted:

```
https://news.google.com/rss/search?q=<query>&hl=en-IN&gl=IN&ceid=IN:en
```

Note: returns Google redirect URLs. Resolve to the publisher URL before hashing.

**Per-channel YouTube** (no key, no quota):
`https://www.youtube.com/feeds/videos.xml?channel_id=<id>`

---

## 2. GDELT DOC 2.0 — chronology, last 3 months

Free. **No API key. No account.** CORS enabled.

```
https://api.gdeltproject.org/api/v2/doc/doc
  ?query=<terms>
  &mode=artlist
  &sort=dateasc
  &maxrecords=250
  &startdatetime=YYYYMMDDHHMMSS
  &enddatetime=YYYYMMDDHHMMSS
  &format=json
```

**Hard limit: rolling 3-month window.** `startdatetime`/`enddatetime` must fall
inside it. Older ranges are not supported.

Returns title, URL, domain, source country, language, publication datetime, and
the social sharing image. **Does not return article body.**

Useful operators inside `query`:

| Operator | Effect |
|---|---|
| `"exact phrase"` | Phrase match |
| `(a OR b)` | Boolean OR |
| `-term` | Exclude |
| `domain:cnn.com` | Restrict to a domain |
| `sourcecountry:india` | Restrict to outlets in a country |
| `sourcelang:english` | Restrict by original language |
| `repeat3:"word"` | Word must appear ≥3× — filters casual mentions |
| `near20:"a b"` | Words within 20 words of each other |

`mode=timelinevolinfo` returns a **coverage-volume timeline** — shows when a story
spiked, with top articles per interval. Free spine for the Timeline tab.

Queries in English match machine-translated coverage across 65 languages.

---

## 3. Deep history — older than 3 months

| Source | Range | Full text | Notes |
|---|---|---|---|
| **Guardian Open Platform** | 1999 → | **Yes** | `from-date`/`to-date`. Free key, 5k calls/day. Best deep-history source |
| **GDELT BigQuery** | Feb 2015 → | No (URLs) | `gdelt-bq.gdeltv2.gkg_partitioned`. **Must filter `_PARTITIONTIME`** or one query burns the 1 TB/month free tier |
| **Wikipedia** | Varies | Yes, CC | Major stories often have a curated timeline article. **Check first** — free, instant, often better than auto-assembly |
| **NYT Archive API** | 1851 → | Abstracts | Metadata spine only |

India-specific deep history is genuinely poor. Expect a thin past and a rich
present for Indian coverage.

---

## 4. Internet Archive

### Read — recover dead URLs. No auth.

```
GET https://archive.org/wayback/available?url=<url>&timestamp=YYYYMMDD
GET http://web.archive.org/cdx/search/cdx?url=<url>&output=json&limit=20
```

**~60 requests/minute.** HTTP 429 on exceed — back off across *all* workers, not
per request.

### Write — Save Page Now. Requires free credentials.

```http
POST https://web.archive.org/save
Authorization: LOW <accesskey>:<secret>
Content-Type: application/x-www-form-urlencoded

url=<article_url>&capture_all=1
```

Credentials: archive.org account → `https://archive.org/account/s3.php`

**6 captures/minute. 7 concurrent sessions.** A capture takes 10–60 seconds, so
this **must** run async off a queue — never in a request cycle.

Caveats: paywalled pages archive as the paywall. Some publishers exclude
themselves. Not a permanence guarantee — it supplements the `read` table, it does
not replace it.

---

## 5. Supplementary APIs

| Source | Endpoint | Limit |
|---|---|---|
| Hacker News | `https://hacker-news.firebaseio.com/v0/topstories.json` | **No rate limit** |
| HN search (better filtering) | `https://hn.algolia.com/api/v1/search?tags=story&numericFilters=points>100` | Free |
| arXiv | `http://export.arxiv.org/api/query?search_query=cat:cs.AI` | 3 s between requests |
| GitHub | `https://api.github.com` | 5,000/hr authenticated |
| Reddit | `https://www.reddit.com/r/<sub>/.rss` | Free |
| Finnhub | company news, quotes | 60 calls/min free |
| CoinGecko | crypto prices | 10,000 calls/month free |

---

## 6. Content rights

*Not legal advice.* The line that matters is **serving**, not **storing**.

| Action | Assessment |
|---|---|
| Reading RSS, storing metadata, showing headline + link | Fine. Publishing a feed invites machine access |
| Storing full text of articles **you opened**, single-user, never served publicly | Personal-copy pattern (Pocket / Instapaper / browser cache). Well established |
| Serving stored full text to anyone else | **Not OK without a licence** |
| Hotlinking `og:image` as a thumbnail with attribution | Intended use — that tag exists to be embedded elsewhere |
| Caching images locally | Heavier exposure than text. Avoid; hotlink instead |
| Full text from Guardian API, Wikipedia, arXiv, SEC EDGAR, PIB | Explicitly reproducible under their licences |
| Triggering Internet Archive snapshots | Fine — IA is a recognised public archive |

**Fetching etiquette, non-negotiable:** honest descriptive User-Agent with a
contact address, respect `robots.txt`, ≤1 request/second per domain, never
parallel-hammer one host. **Never evade bot detection.**

Expect this to get harder: ~79% of top news sites block AI training bots via
`robots.txt`, and Cloudflare began default-blocking mixed-use crawlers on
15 September 2026. Pre-fetching at 04:00 with Wayback fallback is the mitigation.
