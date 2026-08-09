"""ARCHITECTURE.md §12.2. Regenerates the CAPTURED fixtures reproducibly.

Run manually, never by the loop or by pytest. One of exactly two scripts
permitted to touch the real network (the other is scripts/audit_feeds.py;
tests/test_live.py is the one manually-run TEST exception).

Only handles the "Captured" kind from plans/00-implementation-plan.md §5.
"Derived" (malformed/empty/miss) and "Hand-authored" (paywall/consent/js_shell/
cloudflare_403) fixtures are NOT regenerated here - see fixtures/PROVENANCE.md
for how each of those was actually produced; re-derive/re-author by hand if a
real capture underneath them changes shape.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import USER_AGENT  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
INTERVAL = 1.0


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


CAPTURES = [
    # (relative path, url, note)
    ("feeds/with_content_encoded.xml",
     "https://feeds.feedburner.com/ndtvnews-top-stories",
     "NDTV top - audit_feeds.py confirmed has_full_text=true"),
    ("feeds/without_content_encoded.xml",
     "https://techcrunch.com/feed/",
     "TechCrunch - audit_feeds.py confirmed has_full_text=false"),
    ("robots/permissive.txt",
     "https://simonwillison.net/robots.txt",
     "A real, mostly-permissive robots.txt"),
    ("wayback/available_hit.json",
     "https://archive.org/wayback/available"
     "?url=https://en.wikipedia.org/wiki/Python_(programming_language)",
     "Real Wayback availability hit - a URL with deep archive history"),
    # gdelt/artlist.json is NOT captured here - the free DOC 2.0 endpoint
    # 429'd during initial recording (2026-08-09) even at 1 req/sec with a
    # single request. It is hand-authored from the documented response shape
    # in SOURCES.md §2 instead. Re-attempt a real capture here if you want to
    # replace it; see fixtures/PROVENANCE.md before changing its shape.
]


def main() -> int:
    ok = 0
    for rel_path, url, note in CAPTURES:
        dest = FIXTURES / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"{rel_path} <- {url}")
        try:
            body = fetch(url)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            continue
        dest.write_bytes(body)
        print(f"  wrote {len(body)} bytes  ({note})")
        ok += 1
        time.sleep(INTERVAL)

    print(f"\n{ok}/{len(CAPTURES)} captured.")
    return 0 if ok == len(CAPTURES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
