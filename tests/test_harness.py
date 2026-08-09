"""Step 02 acceptance tests. REQUIREMENTS.md R-024..R-027."""

import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import clock
from tests.conftest import NetworkAccessError


def test_network_access_raises():
    """Proves the autouse guard actually blocks a real connection attempt -
    not just that it exists, but that using it fails the way it's supposed
    to. Scoped to CONNECT, not socket() construction - see conftest.py's
    _no_network docstring for why plain construction must stay unguarded."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessError):
            s.connect(("example.com", 443))
    finally:
        s.close()

    with pytest.raises(NetworkAccessError):
        socket.create_connection(("example.com", 443), timeout=1)


def test_loopback_connect_is_not_blocked_by_the_guard():
    """The guard must not block loopback - Windows' asyncio ProactorEventLoop
    (needed by FastAPI's TestClient, used by every web test from step 08 on)
    depends on local socketpair/connect working. Can't assert a SUCCESSFUL
    connect without something listening, so instead assert any exception
    raised is NOT ours."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    try:
        s.connect(("127.0.0.1", 1))  # almost certainly nothing listening there
    except NetworkAccessError:
        pytest.fail("loopback connect must not be blocked by the network guard")
    except OSError:
        pass  # connection refused/timed out - expected; proves it reached the OS
    finally:
        s.close()


def test_clock_is_frozen(frozen_clock):
    first = frozen_clock.now()
    second = frozen_clock.now()
    assert first == second, "frozen clock must not advance between calls"
    assert first == datetime(2026, 8, 9, 4, 0, 0, tzinfo=timezone.utc)

    # re-freezing to simulate time passing (e.g. TTL expiry) must take effect
    later = first + timedelta(days=31)
    frozen_clock.freeze(later)
    assert frozen_clock.now() == later


def test_clock_unfrozen_outside_fixture():
    """Outside the frozen_clock fixture, now() must track the real clock -
    proves freeze/unfreeze doesn't leak state across tests."""
    assert clock._frozen is None
    real = clock.now()
    assert (datetime.now(timezone.utc) - real) < timedelta(seconds=5)


def test_db_is_temporary(temp_db_path: Path, tmp_path: Path):
    assert temp_db_path.parent == tmp_path
    assert temp_db_path.name == "test_aakasavani.db"
    assert not temp_db_path.exists(), "fixture only names the path, doesn't create it"

    real_db = Path(__file__).resolve().parent.parent / "aakasavani.db"
    assert temp_db_path != real_db


def test_all_fixtures_present(fixtures_dir: Path):
    expected = [
        "feeds/with_content_encoded.xml",
        "feeds/without_content_encoded.xml",
        "feeds/malformed.xml",
        "feeds/empty.xml",
        "articles/normal.html",
        "articles/paywall_stub.html",
        "articles/consent_wall.html",
        "articles/js_shell.html",
        "articles/cloudflare_403.html",
        "gdelt/artlist.json",
        "gdelt/empty.json",
        "wayback/available_hit.json",
        "wayback/available_miss.json",
        "robots/permissive.txt",
        "robots/restrictive.txt",
    ]
    missing = [f for f in expected if not (fixtures_dir / f).exists()]
    assert not missing, f"missing fixtures: {missing}"

    for f in expected:
        path = fixtures_dir / f
        assert path.stat().st_size > 0, f"{f} is empty"
