"""ARCHITECTURE.md §6: the budget wrapper. Checks the cap BEFORE calling and
raises BudgetExceeded if the request would breach it - a ledger appended to
after the fact caps nothing.

Rule 4/Rule 1: the reading path (front page, article view) has zero LLM
calls at all, so a budget breach structurally cannot affect it - there's
nothing there to break. This module's job is making sure the ONE place that
DOES call an LLM (the research panel, step 15+) degrades gracefully instead
of crashing when a cap is hit.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from app import clock
from app.config import DAILY_USD_CAP, MONTHLY_USD_CAP, SINGLE_CALL_CAP


class BudgetExceeded(Exception):
    pass


def _day_start_ts(now: datetime) -> int:
    return int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def _month_start_ts(now: datetime) -> int:
    return int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())


def _spent_since(conn: sqlite3.Connection, since_ts: int) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(usd_cost), 0) FROM llm_spend WHERE ts >= ?", (since_ts,)
    ).fetchone()
    return row[0]


def check_before_calling(conn: sqlite3.Connection, estimated_usd: float) -> None:
    """Raises BudgetExceeded BEFORE any Anthropic call is made. Never call
    this after the fact - that's what a ledger-only approach gets wrong."""
    if estimated_usd > SINGLE_CALL_CAP:
        raise BudgetExceeded(
            f"single call estimate ${estimated_usd:.4f} exceeds cap ${SINGLE_CALL_CAP:.2f}"
        )

    now = clock.now()

    day_spent = _spent_since(conn, _day_start_ts(now))
    if day_spent + estimated_usd > DAILY_USD_CAP:
        raise BudgetExceeded(
            f"daily spend ${day_spent:.4f} + ${estimated_usd:.4f} would exceed cap ${DAILY_USD_CAP:.2f}"
        )

    month_spent = _spent_since(conn, _month_start_ts(now))
    if month_spent + estimated_usd > MONTHLY_USD_CAP:
        raise BudgetExceeded(
            f"monthly spend ${month_spent:.4f} + ${estimated_usd:.4f} would exceed cap ${MONTHLY_USD_CAP:.2f}"
        )


def record_spend(conn: sqlite3.Connection, usd_cost: float, *, model: str, purpose: str) -> None:
    conn.execute(
        "INSERT INTO llm_spend (ts, model, purpose, usd_cost) VALUES (?, ?, ?, ?)",
        (int(clock.now().timestamp()), model, purpose, usd_cost),
    )
    conn.commit()


@dataclass
class BudgetedResult:
    text: str | None
    budget_exceeded: bool = False
    error_message: str | None = None


def budgeted_call(
    conn: sqlite3.Connection,
    estimated_usd: float,
    fn,
    *,
    model: str,
    purpose: str,
) -> BudgetedResult:
    """Wraps a call that (a) costs money and (b) might fail. On a budget
    breach, returns a degraded result instead of raising - Rule: a breach
    must never break reading, and must degrade the panel gracefully rather
    than crash it. `fn()` must return (text, actual_usd_cost)."""
    try:
        check_before_calling(conn, estimated_usd)
    except BudgetExceeded:
        return BudgetedResult(
            text=None, budget_exceeded=True, error_message="budget reached for today"
        )

    text, actual_usd_cost = fn()
    record_spend(conn, actual_usd_cost, model=model, purpose=purpose)
    return BudgetedResult(text=text)
