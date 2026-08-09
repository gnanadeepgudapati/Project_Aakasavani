"""The single source of 'now'. Nothing else in app/ may call datetime.now()
or time.time() directly - ARCHITECTURE.md §12.2 requires the clock be
injectable so the edition build's 04:00 IST boundaries, TTL expiry, and
top-up windows are testable without waiting for a wall-clock date.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

_frozen: datetime | None = None


def now() -> datetime:
    """Current time, UTC. Frozen in tests via freeze()/unfreeze()."""
    if _frozen is not None:
        return _frozen
    return datetime.now(timezone.utc)


def now_ist() -> datetime:
    return now().astimezone(IST)


def freeze(dt: datetime) -> None:
    """Test-only. dt must be timezone-aware."""
    global _frozen
    if dt.tzinfo is None:
        raise ValueError("freeze() requires a timezone-aware datetime")
    _frozen = dt.astimezone(timezone.utc)


def unfreeze() -> None:
    global _frozen
    _frozen = None
