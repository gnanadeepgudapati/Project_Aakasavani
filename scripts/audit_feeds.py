"""ARCHITECTURE.md §8 step 01 - the feed audit. NOT a scheduled job; run once
by hand, and re-run only if a feed's format changes.

Fetches each of the 35 frozen feeds exactly once and records, per feed:
  - has_full_text  - does the FIRST item ship <content:encoded>?
  - status         - ok / no_entries / http_error / parse_error
  - checked_at     - ISO timestamp, for the audit trail

Rule 8 applies here too - this is not exempt just because it's a one-time
script. Honest UA, ~1 req/sec, one retry on timeout, no concurrency.

This is one of exactly two scripts permitted to touch the real network
(the other is tests/test_live.py, run manually and never in the verify chain).
"""

import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import FEEDS_YAML_PATH, USER_AGENT  # noqa: E402

REQUEST_INTERVAL_SECONDS = 1.0
TIMEOUT_SECONDS = 15


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return resp.read()


def fetch_with_one_retry(url: str) -> tuple[bytes | None, str]:
    for attempt in (1, 2):
        try:
            return fetch(url), "ok"
        except urllib.error.HTTPError as e:
            return None, f"http_error_{e.code}"
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                return None, f"network_error:{type(e).__name__}"
            time.sleep(REQUEST_INTERVAL_SECONDS)
    return None, "unreachable"


def audit_one(name: str, url: str) -> dict:
    body, status = fetch_with_one_retry(url)
    if body is None:
        return {"has_full_text": None, "status": status, "entry_count": 0}

    parsed = feedparser.parse(body)
    if not parsed.entries:
        bozo = " (bozo)" if parsed.bozo else ""
        return {"has_full_text": None, "status": f"no_entries{bozo}", "entry_count": 0}

    first = parsed.entries[0]
    has_content = bool(getattr(first, "content", None) and first.content[0].value.strip())
    return {
        "has_full_text": has_content,
        "status": "ok",
        "entry_count": len(parsed.entries),
    }


def main() -> int:
    with open(FEEDS_YAML_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    feeds = data["feeds"]
    failures = []

    for i, feed in enumerate(feeds, 1):
        print(f"[{i}/{len(feeds)}] {feed['name']} -> {feed['url']}", flush=True)
        result = audit_one(feed["name"], feed["url"])
        feed["has_full_text"] = result["has_full_text"]
        feed["_audit_status"] = result["status"]
        feed["_audit_entry_count"] = result["entry_count"]
        feed["_audited_at"] = datetime.now(timezone.utc).isoformat()

        marker = "OK " if result["has_full_text"] is not None else "FAIL"
        print(f"    [{marker}] {result['status']}, "
              f"has_full_text={result['has_full_text']}, "
              f"entries={result['entry_count']}", flush=True)

        if result["has_full_text"] is None:
            failures.append((feed["name"], feed["url"], result["status"]))

        if i < len(feeds):
            time.sleep(REQUEST_INTERVAL_SECONDS)

    with open(FEEDS_YAML_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True, width=100)

    print(f"\n{len(feeds) - len(failures)}/{len(feeds)} audited successfully.")
    if failures:
        print(f"\n{len(failures)} FAILURES - not silently substituted, per "
              f"SOURCES.md §1's frozen-list warning. Log to BLOCKED.md:")
        for name, url, status in failures:
            print(f"  - {name}: {status} ({url})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
