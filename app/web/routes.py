"""Feed view (step 08) + article view (step 09).

EDITION-AND-UI.md §0: the app serves a finished EDITION, not a river.
S-008: front-page (pre-fetched) articles never touch the network on open;
"show everything" articles fetch on click, by design.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import clock
from app.config import SECTIONS
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


def _render_edition(request: Request, conn, edition, section_filter: str | None):
    if edition is None:
        # Rule 7: never an empty page - but there's genuinely nothing built
        # yet on a brand-new install. An honest "not built yet" state, not
        # a crash.
        return templates.TemplateResponse(
            request, "empty.html", {"message": "No edition has been built yet."}
        )

    sections = _edition_sections(conn, edition["id"], section_filter)
    remainder = _remainder(conn, edition["id"]) if section_filter is None else []
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "edition": edition,
            "sections": sections,
            "all_sections": SECTIONS,
            "active_section": section_filter,
            "remainder": remainder,
        },
    )


# ── feed view (step 08) ─────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def front_page(
    request: Request,
    section: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    edition = _get_live_edition(conn)
    return _render_edition(request, conn, edition, section_filter=section)


@router.get("/edition/{date}", response_class=HTMLResponse)
def edition_by_date(
    request: Request,
    date: str,
    section: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    edition = _get_edition_by_date(conn, date)
    if edition is None:
        raise HTTPException(status_code=404, detail="No edition for this date")
    return _render_edition(request, conn, edition, section_filter=section)


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
