"""Feed view (step 08) + article view (step 09).

EDITION-AND-UI.md §0: the app serves a finished EDITION, not a river.
S-008: front-page (pre-fetched) articles never touch the network on open;
"show everything" articles fetch on click, by design.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import clock
from app.config import SECTIONS
from app.search import search_read
from app.topics import add_topic, list_topics, match_topic
from app.web.deps import get_db
from app.web.sanitize import sanitize_description

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["sanitize"] = sanitize_description


# ── queries ──────────────────────────────────────────────────────────────

def _get_live_edition(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT * FROM editions WHERE status = 'live' ORDER BY built_at DESC LIMIT 1"
    ).fetchone()


def _get_edition_by_date(conn: sqlite3.Connection, date_str: str):
    return conn.execute(
        "SELECT * FROM editions WHERE edition_date = ? "
        "AND status IN ('live', 'superseded') ORDER BY built_at DESC LIMIT 1",
        (date_str,),
    ).fetchone()


def _edition_sections(conn: sqlite3.Connection, edition_id: int, section_filter: str | None):
    wanted = [section_filter] if section_filter else list(SECTIONS)
    result = {}
    for section in wanted:
        rows = conn.execute(
            "SELECT s.*, ei.rank_position FROM edition_items ei "
            "JOIN seen s ON s.url_hash = ei.url_hash "
            "WHERE ei.edition_id = ? AND ei.section = ? "
            "ORDER BY ei.rank_position ASC",
            (edition_id, section),
        ).fetchall()
        result[section] = rows
    return result


def _remainder(conn: sqlite3.Connection, edition_id: int):
    """EDITION-AND-UI.md "Show everything (213 more)": seen rows not on the
    front page, most recent first."""
    return conn.execute(
        "SELECT * FROM seen WHERE expired = 0 AND url_hash NOT IN "
        "(SELECT url_hash FROM edition_items WHERE edition_id = ?) "
        "ORDER BY published_at DESC LIMIT 200",
        (edition_id,),
    ).fetchall()


def _topic_chip_data(topics, active_topic: str | None, active_section: str | None):
    """plans/27-ui-completion.md G-2: precomputed hrefs so index.html's chip
    loop stays a plain Jinja loop - EDITION-AND-UI.md §2.3's "combinable"
    section+topic chips, and re-clicking the active topic clears it."""
    chips = []
    for t in topics:
        is_active = active_topic == t["name"]
        params = []
        if not is_active:
            params.append(f"topic={quote(t['name'])}")
        if active_section:
            params.append(f"section={quote(active_section)}")
        href = "/" + ("?" + "&".join(params) if params else "")
        chips.append({"name": t["name"], "href": href, "active": is_active})
    return chips


def _render_edition(
    request: Request,
    conn,
    edition,
    section_filter: str | None,
    topic_filter: str | None = None,
):
    topics = list_topics(conn)
    topic_chips = _topic_chip_data(topics, topic_filter, section_filter)

    if topic_filter:
        # G-2: EDITION-AND-UI.md §2.2 - a topic is a saved query, "retroactive
        # instantly - matches the whole history." That means matching against
        # ALL of `seen`, not just today's front page (_edition_sections below
        # only ever looks at edition_items) - a topic view is a different,
        # wider query, not a narrowing of the edition.
        try:
            matched = match_topic(conn, topic_filter)
        except KeyError:
            raise HTTPException(status_code=404, detail="No such topic")
        if section_filter:
            matched = [r for r in matched if r["section"] == section_filter]

        wanted = [section_filter] if section_filter else list(SECTIONS)
        sections = {s: [] for s in wanted}
        for row in matched:
            if row["section"] in sections:
                sections[row["section"]].append(row)

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "edition": edition,
                "sections": sections,
                "all_sections": SECTIONS,
                "active_section": section_filter,
                "active_topic": topic_filter,
                "topic_chips": topic_chips,
                "remainder": [],
            },
        )

    if edition is None:
        # Rule 7: never an empty page - but there's genuinely nothing built
        # yet on a brand-new install. An honest "not built yet" state, not
        # a crash.
        return templates.TemplateResponse(
            request, "empty.html", {"message": "No edition has been built yet."}
        )

    sections = _edition_sections(conn, edition["id"], section_filter)

    # "Show everything" is the current full ingest beyond TODAY's front
    # page - it doesn't make sense attached to a past (superseded) edition,
    # where it would mix in articles that didn't exist yet on that date.
    # Caught by test_edition_by_date: browsing a past date was leaking a
    # later article into its remainder section.
    show_remainder = section_filter is None and edition["status"] == "live"
    remainder = _remainder(conn, edition["id"]) if show_remainder else []
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "edition": edition,
            "sections": sections,
            "all_sections": SECTIONS,
            "active_section": section_filter,
            "active_topic": None,
            "topic_chips": topic_chips,
            "remainder": remainder,
        },
    )


# ── feed view (step 08) ─────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def front_page(
    request: Request,
    section: str | None = None,
    topic: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    edition = _get_live_edition(conn)
    return _render_edition(request, conn, edition, section_filter=section, topic_filter=topic)


@router.get("/edition/{date}", response_class=HTMLResponse)
def edition_by_date(
    request: Request,
    date: str,
    section: str | None = None,
    topic: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    edition = _get_edition_by_date(conn, date)
    if edition is None:
        raise HTTPException(status_code=404, detail="No edition for this date")
    return _render_edition(request, conn, edition, section_filter=section, topic_filter=topic)


# ── topics (step 27, G-2) ────────────────────────────────────────────────

@router.post("/topics")
def create_topic(
    name: str = Form(...),
    query: str = Form(...),
    conn: sqlite3.Connection = Depends(get_db),
):
    """The "+ new" control (EDITION-AND-UI.md §2.3): "opens a box to type a
    query - the whole topic system is user-editable at runtime." Wraps the
    existing app.topics.add_topic() - topics.name is UNIQUE, so a duplicate
    name is a 400, not a raw IntegrityError 500."""
    name = name.strip()
    query = query.strip()
    if not name or not query:
        raise HTTPException(status_code=400, detail="name and query are both required")
    try:
        add_topic(conn, name, query)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"a topic named {name!r} already exists")
    return RedirectResponse(url="/", status_code=303)


# ── search (step 27, G-3) ────────────────────────────────────────────────

@router.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    q: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    """search.py's own docstring: `read`/`read_fts` only, never `seen` -
    the personal-reading-history boundary. An empty/blank query renders the
    page with no results rather than handing an empty string to FTS5's
    MATCH, which raises OperationalError."""
    query = (q or "").strip()
    results = search_read(conn, query) if query else []
    return templates.TemplateResponse(
        request, "search.html", {"query": query, "results": results}
    )


# ── article view (step 09) ──────────────────────────────────────────────

class DwellPayload(BaseModel):
    dwell_seconds: int


@router.get("/article/{url_hash_hex}", response_class=HTMLResponse)
def article_view(
    request: Request,
    url_hash_hex: str,
    conn: sqlite3.Connection = Depends(get_db),
):
    h = bytes.fromhex(url_hash_hex)

    # ARCHITECTURE.md Flow B: already read? serve the stored copy instantly.
    read_row = conn.execute("SELECT * FROM read WHERE url_hash = ?", (h,)).fetchone()
    if read_row is not None:
        return templates.TemplateResponse(request, "article.html", {"article": read_row})

    seen_row = conn.execute("SELECT * FROM seen WHERE url_hash = ?", (h,)).fetchone()
    if seen_row is None:
        raise HTTPException(status_code=404)

    if seen_row["full_text"]:
        # Front-page item - already pre-fetched at 04:00. No network here.
        full_text = seen_row["full_text"]
        fetched_via = seen_row["fetched_via"]
    else:
        # S-008: "show everything" item, never pre-fetched - fetch now, on
        # click, by design (EDITION-AND-UI.md: "fetched on click, not
        # pre-fetched"). The only reading-path route allowed to do this.
        from app.net.fetcher import Fetcher

        result = Fetcher().get_full_text(seen_row["canonical_url"])
        full_text = result.text
        fetched_via = result.fetched_via

    now = int(clock.now().timestamp())
    conn.execute(
        "INSERT INTO read (url_hash, canonical_url, title, source, published_at, "
        "full_text, fetched_via, read_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            h, seen_row["canonical_url"], seen_row["title"], seen_row["source"],
            seen_row["published_at"], full_text, fetched_via, now,
        ),
    )
    conn.commit()

    read_row = conn.execute("SELECT * FROM read WHERE url_hash = ?", (h,)).fetchone()
    return templates.TemplateResponse(request, "article.html", {"article": read_row})


@router.post("/article/{url_hash_hex}/close")
def article_close(
    url_hash_hex: str,
    payload: DwellPayload,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Rule 9: log dwell_seconds. Called by app.js when the reader navigates
    away - see app/web/static/app.js."""
    h = bytes.fromhex(url_hash_hex)
    conn.execute(
        "UPDATE read SET dwell_seconds = ? WHERE url_hash = ?",
        (payload.dwell_seconds, h),
    )
    conn.commit()
    return {"ok": True}
