"""Step 14 acceptance tests. REQUIREMENTS.md R-075..R-079."""

import pytest

from app.config import DAILY_USD_CAP, MONTHLY_USD_CAP, SINGLE_CALL_CAP
from app.research.budget import BudgetExceeded, budgeted_call, check_before_calling, record_spend


def test_raises_before_calling(db_conn, frozen_clock):
    """R-075. The check must happen BEFORE fn() runs, not after - proven by
    a spy fn that explodes if it's ever invoked, with the budget already
    exhausted."""
    record_spend(db_conn, DAILY_USD_CAP, model="claude-haiku-4-5-20251001", purpose="test")

    def must_not_be_called():
        raise AssertionError("fn() must never run once the cap check fails")

    result = budgeted_call(db_conn, 0.01, must_not_be_called, model="m", purpose="p")
    assert result.budget_exceeded is True
    assert result.text is None


def test_single_call_cap(db_conn, frozen_clock):
    """R-076."""
    with pytest.raises(BudgetExceeded):
        check_before_calling(db_conn, SINGLE_CALL_CAP + 0.01)

    check_before_calling(db_conn, SINGLE_CALL_CAP)  # exactly at cap - must not raise


def test_daily_cap(db_conn, frozen_clock):
    """R-077."""
    record_spend(db_conn, DAILY_USD_CAP - 0.005, model="m", purpose="p")

    with pytest.raises(BudgetExceeded):
        check_before_calling(db_conn, 0.01)  # would push over DAILY_USD_CAP

    check_before_calling(db_conn, 0.001)  # still under - must not raise


def test_monthly_cap(db_conn, frozen_clock):
    """R-078."""
    # Spread small amounts across several days this month, all under the
    # daily cap individually, but summing close to the monthly cap.
    from datetime import timedelta

    base = frozen_clock.now()
    per_day = DAILY_USD_CAP - 0.01
    days_needed = int(MONTHLY_USD_CAP // per_day)

    for i in range(days_needed):
        frozen_clock.freeze(base - timedelta(days=i))
        record_spend(db_conn, per_day, model="m", purpose="p")

    frozen_clock.freeze(base)  # back to "today"

    with pytest.raises(BudgetExceeded):
        check_before_calling(db_conn, MONTHLY_USD_CAP)  # would clearly exceed


def test_breach_does_not_break_reading(db_conn, frozen_clock):
    """R-079. A budget breach must degrade the panel only - the reading
    path has no LLM calls at all (Rule 4), so it cannot be affected
    structurally, and budgeted_call() itself must degrade rather than raise
    all the way up to a caller."""
    from fastapi.testclient import TestClient

    from app.web.deps import get_db
    from app.web.main import app

    record_spend(db_conn, MONTHLY_USD_CAP, model="m", purpose="p")

    # budgeted_call degrades gracefully, does not raise
    result = budgeted_call(db_conn, 0.01, lambda: ("should not run", 0.01), model="m", purpose="p")
    assert result.budget_exceeded is True
    assert result.error_message == "budget reached for today"

    # the reading path is completely unaffected
    app.dependency_overrides[get_db] = lambda: db_conn
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    app.dependency_overrides.clear()
