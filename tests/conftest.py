"""Fixtures only. ARCHITECTURE.md §12.2.

Three guarantees every test in this suite gets for free:
  - no network is reachable at all (session-scoped, autouse)
  - the clock is frozen and explicit
  - the DB is a fresh temp file, never the real aakasavani.db

tests/test_live.py is the one manually-run exception to the network ban and
does NOT import this file's autouse guard in a way that would block it -
it is excluded from testpaths entirely (see pyproject.toml) and run directly.
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import clock as clock_module


class NetworkAccessError(RuntimeError):
    """Raised instead of letting any test touch a real socket."""


def _blocked_socket(*args, **kwargs):
    raise NetworkAccessError(
        "tests must never touch the network - ARCHITECTURE.md §12.2. "
        "Use a fixture, or mark the test skip-guarded in test_live.py."
    )


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Session-wide network ban, reapplied per-test so no test can quietly
    monkeypatch it back open for the rest of the run."""
    monkeypatch.setattr(socket, "socket", _blocked_socket)
    monkeypatch.setattr(socket, "create_connection", _blocked_socket)
    yield


@pytest.fixture
def frozen_clock():
    """Freezes app.clock.now() to a fixed instant. Callers can re-freeze to
    a different instant mid-test to simulate time passing (e.g. TTL expiry)."""
    fixed = datetime(2026, 8, 9, 4, 0, 0, tzinfo=timezone.utc)  # 09:30 IST
    clock_module.freeze(fixed)
    yield clock_module
    clock_module.unfreeze()


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_aakasavani.db"


@pytest.fixture
def db_conn(temp_db_path):
    """A fresh, migrated, temporary SQLite connection. Never the real DB -
    temp_db_path lives under pytest's tmp_path, deleted after the test.

    Imports app.db lazily (step 04) so tests that don't request this fixture
    can collect and run before step 04 exists.
    """
    from app import db as db_module

    conn = db_module.connect(temp_db_path)
    db_module.migrate(conn)
    yield conn
    conn.close()


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


def read_fixture(*parts: str) -> bytes:
    """Read a fixture file as bytes - byte-exact, per plans/00-implementation-plan.md §5."""
    path = FIXTURES_DIR.joinpath(*parts)
    return path.read_bytes()
