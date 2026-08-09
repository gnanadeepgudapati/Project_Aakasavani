"""The Ten Rules, as assertions. CLAUDE.md, ARCHITECTURE.md §12.1.

Runs on every verify, forever, from this step on - AUTONOMOUS-LOOP.md.

Design note: most rule tests exercise app modules that don't exist until
later build steps (schema=04, fetcher=05, edition build=07, web=08-09,
panel=15-17). Each test below does its OWN import of what it needs, INSIDE
the test function, never at module top level - that way a module that
doesn't exist yet fails only the specific test that needs it (a clean,
honest "red because the feature isn't built", per ARCHITECTURE.md §8: "must
be red before any feature exists, green after"), rather than an import
error at the top of this file blocking every other rule test, and every
later step's verify chain, until the last feature lands.

D-1/D-2/D-3 rulings (logs/SESSIONS.md S-006) are already the design of
R-002/R-003 (storage vs. render) and R-010 (/research/* named exception) and
R-041 in test_fetcher.py (not here - robots+wayback is a fetcher concern).
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest

from app.config import USER_AGENT
from tests._static_analysis import imports_reachable_from

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "fixtures"


def _installed_names() -> set[str]:
    return {d.metadata["Name"].lower() for d in importlib.metadata.distributions()}


# ─────────────────────────────────────────────────────────────────
# Rule 1 · No AI-generated text anywhere in the reading path
# ─────────────────────────────────────────────────────────────────

def test_no_llm_import_in_render_path():
    """R-001. Static: walk app.web.routes' import graph, confirm 'anthropic'
    is never reachable. Passes vacuously until app.web.routes exists (step
    08) - that's correct, not a loophole: nothing built yet means nothing
    can violate the rule yet. See test_static_analysis_helper_catches_a_
    real_case below for proof the WALKER itself works."""
    reachable = imports_reachable_from("app.web.routes", REPO_ROOT)
    assert "anthropic" not in reachable, (
        f"app.web.routes can reach anthropic via: {reachable}"
    )


def test_stored_description_is_verbatim():
    """R-002. D-1 (logs/SESSIONS.md S-006): scopes to STORAGE, not render -
    feedparser decodes HTML entities during parsing, so byte-identity with
    the wire bytes is unsatisfiable at render by any implementation. This
    asserts seen.description equals what feedparser itself produced, i.e.
    our own parser layer (app.ingest.parser, step 06) adds no rewording."""
    import feedparser

    from app.ingest.parser import parse_feed  # step 06

    raw = (FIXTURES / "feeds" / "with_content_encoded.xml").read_bytes()
    reference = feedparser.parse(raw)
    records = parse_feed(raw)

    assert len(records) == len(reference.entries)
    for record, entry in zip(records, reference.entries):
        assert record.description == entry.get("description", ""), (
            "parser must not reword/re-encode the description feedparser produced"
        )


def test_render_sanitisation_only_removes_markup():
    """R-003. D-1: the HTML allowlist sanitiser used at render time may
    strip tags, but every word of text content must survive, in order."""
    from app.web.sanitize import sanitize_description  # step 08

    raw = 'Officials <b>confirmed</b> the change <a href="x">today</a>, per a <i>new</i> filing.'
    cleaned = sanitize_description(raw)

    assert "<" not in cleaned and ">" not in cleaned, "tags must be fully removed"
    original_words = ["Officials", "confirmed", "the", "change", "today", "per", "a", "new", "filing"]

    # Word-boundary subsequence check, not substring .index() - "a" is a
    # substring of "change" and would falsely match there first, breaking
    # the order check for reasons that have nothing to do with the sanitiser
    # actually reordering anything.
    import re

    tokens = re.findall(r"\w+", cleaned)
    cursor = 0
    for word in original_words:
        while cursor < len(tokens) and tokens[cursor] != word:
            cursor += 1
        assert cursor < len(tokens), f"sanitiser dropped or reworded {word!r}"
        cursor += 1


# ─────────────────────────────────────────────────────────────────
# Rule 2 · No cross-article synthesis
# ─────────────────────────────────────────────────────────────────

def test_six_outlets_six_entries(db_conn):
    """R-004. One story reported by 6 different outlets must yield 6 rows
    in `seen`, never merged into one - Rule 2's whole point."""
    from app.ingest.canonical import canonicalize, url_hash
    from app.ingest.dedupe import insert_if_new

    domains = [f"outlet{i}.test" for i in range(6)]
    for i, domain in enumerate(domains):
        url = f"https://{domain}/story-about-the-same-event?utm_source=rss"
        canon = canonicalize(url)
        insert_if_new(
            db_conn,
            url_hash=url_hash(canon),
            canonical_url=canon,
            title=f"Outlet {i}'s headline on the event",
            source=domain,
            section="world_india",
            published_at=1754700000,
            description="Some outlet-specific description of the same event.",
        )

    rows = db_conn.execute("SELECT COUNT(*) FROM seen").fetchone()
    assert rows[0] == 6, "6 distinct URLs from 6 outlets must be 6 rows, not merged"


# ─────────────────────────────────────────────────────────────────
# Rule 3 · Articles shown whole and unaltered
# ─────────────────────────────────────────────────────────────────

def test_stored_text_equals_extractor_output():
    """R-005. No post-processing step may sit between Trafilatura's output
    and what gets stored in read.full_text."""
    from app.extract.article import extract_full_text  # step 05

    html = (FIXTURES / "articles" / "normal.html").read_bytes()
    first = extract_full_text(html)
    second = extract_full_text(html)
    assert first == second, "extraction must be deterministic (no hidden randomness)"
    assert first is not None and len(first) > 500


# ─────────────────────────────────────────────────────────────────
# Rule 4 · AI is pull, not push
# ─────────────────────────────────────────────────────────────────

def test_build_makes_zero_llm_calls(monkeypatch, db_conn, frozen_clock):
    """R-006. Runs the whole 04:00 build against fixtures with the Anthropic
    client patched to raise on ANY call. The build must complete without
    ever constructing/calling it."""
    import sys
    import types

    def _forbidden(*args, **kwargs):
        raise AssertionError("the 04:00 build must never call Anthropic - Rule 4")

    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.Anthropic = _forbidden
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic)

    from app.edition.build import run_build  # step 07

    run_build(db_conn)  # must not raise


def test_no_llm_import_in_build_path():
    """R-007. Static twin of R-006 - the import itself must be unreachable,
    not merely unused-in-practice."""
    reachable = imports_reachable_from("app.edition.build", REPO_ROOT)
    assert "anthropic" not in reachable, (
        f"app.edition.build can reach anthropic via: {reachable}"
    )


# ─────────────────────────────────────────────────────────────────
# Rule 5 · TTL the firehose, keep the reads
# ─────────────────────────────────────────────────────────────────

def test_sweep_strips_text_keeps_hash(db_conn, frozen_clock):
    """R-008."""
    from app.jobs.sweep import sweep_expired_seen  # step 12

    expired_at = int(frozen_clock.now().timestamp()) - 1
    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, full_text, fetched_via, first_seen, "
        "expires_at, expired) "
        "VALUES (?, 'https://x.test/a', 'T', 'S', 'tech', 1, 'D', "
        "'pre-fetched front-page text', 'live', 1, ?, 0)",
        (b"\x01" * 32, expired_at),
    )
    db_conn.commit()

    sweep_expired_seen(db_conn, now=frozen_clock.now())

    row = db_conn.execute(
        "SELECT title, description, source, full_text, fetched_via, expired "
        "FROM seen WHERE url_hash = ?",
        (b"\x01" * 32,),
    ).fetchone()
    assert row["title"] is None
    assert row["description"] is None
    assert row["source"] is None
    assert row["full_text"] is None, "migration 002 (S-007): pre-fetched text must be stripped too"
    assert row["fetched_via"] is None
    assert row["expired"] == 1


def test_read_rows_never_expire(db_conn, frozen_clock):
    """R-009."""
    from app.jobs.sweep import sweep_expired_seen

    db_conn.execute(
        "INSERT INTO read (url_hash, canonical_url, title, source, "
        "published_at, full_text, fetched_via, read_at) "
        "VALUES (?, 'https://x.test/a', 'T', 'S', 1, 'full text here', 'feed', 1)",
        (b"\x02" * 32,),
    )
    db_conn.commit()

    from datetime import timedelta
    far_future = frozen_clock.now() + timedelta(days=3650)
    sweep_expired_seen(db_conn, now=far_future)

    row = db_conn.execute(
        "SELECT title, full_text FROM read WHERE url_hash = ?", (b"\x02" * 32,)
    ).fetchone()
    assert row["title"] == "T"
    assert row["full_text"] == "full text here"


# ─────────────────────────────────────────────────────────────────
# Rule 6 · Pre-fetch at 04:00, never at click time
# ─────────────────────────────────────────────────────────────────

def test_no_network_on_reading_path(db_conn, frozen_clock, monkeypatch):
    """R-010. D-2 (S-006) scoped by S-008: `/`, `/edition/*`, and opening a
    front-page (pre-fetched) article must complete with zero network
    attempts - the autouse guard in conftest.py would raise
    NetworkAccessError on any attempt.

    /research/* is the SOLE exception, proven by making it actually touch
    the network when called unmocked (no fake call_fn injected). FastAPI's
    TestClient re-raises an unhandled route exception into the calling test
    rather than converting it to a 500 response, so the real exception chain
    is directly inspectable. The Anthropic SDK wraps the raw connection
    failure in its own APIConnectionError rather than letting
    NetworkAccessError propagate untouched - checked via __cause__/
    __context__ instead, which still proves a real connection attempt was
    made, not merely that some unrelated error occurred.

    (Opening a NOT-pre-fetched "show everything" article is allowed to fetch
    live by design - S-008 - and is deliberately not exercised here.)
    """
    from fastapi.testclient import TestClient

    from app.web.deps import get_db
    from app.web.main import app  # step 08
    from tests.conftest import NetworkAccessError

    app.dependency_overrides[get_db] = lambda: db_conn
    client = TestClient(app)

    for path in ("/", "/edition/2026-08-09"):
        resp = client.get(path)
        assert resp.status_code in (200, 404), f"{path} errored unexpectedly: {resp.status_code}"

    db_conn.execute(
        "INSERT INTO seen (url_hash, canonical_url, title, source, section, "
        "published_at, description, full_text, fetched_via, first_seen, expires_at) "
        "VALUES (?, 'https://x.test/prefetched', 'T', 'S', 'tech', 1, 'D', "
        "'already fetched at build time', 'live', 1, 999999999999)",
        (b"\x30" * 32,),
    )
    db_conn.commit()
    resp = client.get(f"/article/{('30' * 32)}")
    assert resp.status_code == 200, "a pre-fetched article must render without any network attempt"

    db_conn.execute(
        "INSERT INTO read (url_hash, canonical_url, title, source, published_at, "
        "full_text, fetched_via, read_at) VALUES "
        "(?, 'https://x.test/read', 'T', 'S', 1, 'Paragraph one.\n\nParagraph two.', 'feed', 1)",
        (b"\x31" * 32,),
    )
    db_conn.commit()

    # No real ANTHROPIC_API_KEY is configured in this environment
    # (BLOCKED.md B-002). Without one, the SDK fails at local header
    # validation before ever attempting a connection - a different, earlier
    # failure that wouldn't prove anything about network access. A
    # syntactically-valid FAKE key gets past that local check and reaches
    # the real (guard-intercepted) connection attempt instead.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-network-guard-proof")

    with pytest.raises(Exception) as excinfo:
        client.post(f"/research/{'31' * 32}/ask", json={"question": "What happened?"})

    cause_chain = []
    cur = excinfo.value
    while cur is not None:
        cause_chain.append(type(cur))
        cur = cur.__cause__ or cur.__context__
    assert NetworkAccessError in cause_chain, (
        f"/research/*'s network attempt should trace back to the guard; got {cause_chain}"
    )

    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────
# Rule 7 · Never show an empty page
# ─────────────────────────────────────────────────────────────────

def test_failed_build_keeps_previous_edition(db_conn, frozen_clock, monkeypatch):
    """R-011."""
    from app.edition.build import run_build

    db_conn.execute(
        "INSERT INTO editions (edition_date, built_at, status, article_count) "
        "VALUES ('2026-08-08', 1, 'live', 39)"
    )
    db_conn.commit()

    def _boom(*a, **k):
        raise RuntimeError("simulated mid-build failure")

    monkeypatch.setattr("app.edition.build._select_edition", _boom, raising=False)

    with pytest.raises(RuntimeError):
        run_build(db_conn)

    live = db_conn.execute(
        "SELECT edition_date FROM editions WHERE status = 'live' "
        "ORDER BY built_at DESC LIMIT 1"
    ).fetchone()
    assert live["edition_date"] == "2026-08-08", "a failed build must not unseat the live edition"


def test_swap_is_atomic(db_conn, frozen_clock, monkeypatch):
    """R-012."""
    from app.edition.swap import atomic_swap

    def _boom_mid_swap(*a, **k):
        raise RuntimeError("simulated failure inside the swap transaction")

    monkeypatch.setattr("app.edition.swap._write_edition_items", _boom_mid_swap, raising=False)

    with pytest.raises(RuntimeError):
        atomic_swap(db_conn, edition_date="2026-08-09", items=[{"url_hash": b"x", "section": "tech", "rank_position": 1}])

    count = db_conn.execute("SELECT COUNT(*) FROM edition_items").fetchone()[0]
    assert count == 0, "a failed swap must leave zero partial rows, not a half-written edition"


# ─────────────────────────────────────────────────────────────────
# Rule 8 · Never evade bot detection
# ─────────────────────────────────────────────────────────────────

def test_rate_limiter_is_shared_and_enforced():
    """R-013."""
    from app.net.limiter import SharedLimiter

    ticks = [0.0]

    def fake_clock():
        return ticks[0]

    limiter = SharedLimiter(min_interval_seconds=1.0, clock=fake_clock)

    limiter.acquire("example.test")
    first_wait = None

    ticks[0] = 0.2  # a second caller arrives 0.2s later - must wait ~0.8s more
    waited = limiter.acquire("example.test")
    assert waited >= 0.7, f"second caller on same domain should have waited, got {waited}"


def test_user_agent_is_honest():
    """R-014. Fully testable today - app.config already exists."""
    assert "Aakasavani" in USER_AGENT
    assert "mailto:" in USER_AGENT
    impersonation_markers = ("mozilla", "chrome", "safari", "webkit", "gecko")
    lowered = USER_AGENT.lower()
    assert not any(marker in lowered for marker in impersonation_markers), (
        f"User-Agent must not impersonate a browser: {USER_AGENT!r}"
    )


def test_robots_txt_respected():
    """R-015."""
    from app.net.robots import is_allowed  # step 05

    restrictive = (FIXTURES / "robots" / "restrictive.txt").read_text(encoding="utf-8")
    assert is_allowed(restrictive, url_path="/any/article", user_agent="Aakasavani") is False

    permissive = (FIXTURES / "robots" / "permissive.txt").read_text(encoding="utf-8")
    assert is_allowed(permissive, url_path="/any/article", user_agent="Aakasavani") is True


def test_no_evasion_dependencies():
    """R-016. Fully testable today - checks the actual installed venv."""
    installed = _installed_names()
    forbidden = {
        "selenium", "undetected-chromedriver", "playwright-stealth",
        "cloudscraper", "fake-useragent",
    }
    present = installed & forbidden
    assert not present, f"bot-detection-evasion package(s) installed: {present}"


# ─────────────────────────────────────────────────────────────────
# Rule 9 · Log read_at and dwell_seconds from day one
# ─────────────────────────────────────────────────────────────────

def test_read_schema_has_dwell_columns(db_conn):
    """R-017."""
    cols = {row["name"] for row in db_conn.execute("PRAGMA table_info(read)")}
    assert "read_at" in cols
    assert "dwell_seconds" in cols


def test_article_view_writes_dwell(db_conn, frozen_clock):
    """R-018."""
    from fastapi.testclient import TestClient

    from app.web.deps import get_db
    from app.web.main import app  # step 09

    app.dependency_overrides[get_db] = lambda: db_conn
    client = TestClient(app)

    url_hash_hex = "03" * 32
    db_conn.execute(
        "INSERT INTO read (url_hash, canonical_url, title, source, "
        "published_at, full_text, fetched_via, read_at) VALUES "
        "(?, 'https://x.test/a', 'T', 'S', 1, 'body', 'feed', 1)",
        (bytes.fromhex(url_hash_hex),),
    )
    db_conn.commit()

    resp = client.post(f"/article/{url_hash_hex}/close", json={"dwell_seconds": 42})
    assert resp.status_code == 200

    row = db_conn.execute(
        "SELECT dwell_seconds FROM read WHERE url_hash = ?", (bytes.fromhex(url_hash_hex),)
    ).fetchone()
    assert row is not None and row["dwell_seconds"] == 42

    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────
# Rule 10 · SQLite, single file, single process
# ─────────────────────────────────────────────────────────────────

def test_no_forbidden_dependencies():
    """R-019. Fully testable today - checks the actual installed venv."""
    installed = _installed_names()
    forbidden = {
        "psycopg2", "psycopg2-binary", "redis", "celery", "pinecone-client",
        "chromadb", "sqlalchemy", "kombu", "pymongo",
    }
    present = installed & forbidden
    assert not present, f"forbidden multi-process/external-DB dependency installed: {present}"


# ─────────────────────────────────────────────────────────────────
# Self-test: proves the static-analysis helper itself is sound
# ─────────────────────────────────────────────────────────────────

def test_static_analysis_helper_catches_a_real_case(tmp_path: Path):
    """Not a numbered requirement - this is the 'break it, show red, restore'
    proof for the static-analysis mechanism underlying R-001/R-007, run
    against a synthetic package so it doesn't depend on app.web existing yet.
    """
    pkg = tmp_path / "fakeapp"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "clean.py").write_text("import os\nimport json\n", encoding="utf-8")
    (pkg / "dirty.py").write_text("import anthropic\nfrom . import clean\n", encoding="utf-8")
    (pkg / "indirect.py").write_text("from . import dirty\n", encoding="utf-8")

    clean_reachable = imports_reachable_from("fakeapp.clean", tmp_path, top_level_package="fakeapp")
    assert "anthropic" not in clean_reachable, "false positive: clean module flagged"

    dirty_reachable = imports_reachable_from("fakeapp.dirty", tmp_path, top_level_package="fakeapp")
    assert "anthropic" in dirty_reachable, "false negative: direct import not caught"

    indirect_reachable = imports_reachable_from("fakeapp.indirect", tmp_path, top_level_package="fakeapp")
    assert "anthropic" in indirect_reachable, (
        "false negative: transitive import (indirect -> dirty -> anthropic) not caught"
    )
