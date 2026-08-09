"""Rule 8: one shared limiter object every outbound fetch passes through.
No caller may bypass it. ARCHITECTURE.md §6.
"""

from __future__ import annotations

import threading
import time


class SharedLimiter:
    """Per-domain rate limiting. Clock and sleep are injectable so tests can
    verify the WAIT CALCULATION without actually sleeping."""

    def __init__(
        self,
        min_interval_seconds: float = 1.0,
        clock=time.monotonic,
        sleep=time.sleep,
    ) -> None:
        self._min_interval = min_interval_seconds
        self._clock = clock
        self._sleep = sleep
        self._last_call: dict[str, float] = {}
        self._lock = threading.Lock()

    def acquire(self, domain: str) -> float:
        """Blocks (via self._sleep) until at least min_interval_seconds have
        passed since the last acquire() for this domain. Returns how long it
        waited, for testability."""
        with self._lock:
            now = self._clock()
            last = self._last_call.get(domain)
            waited = 0.0
            if last is not None:
                elapsed = now - last
                if elapsed < self._min_interval:
                    waited = self._min_interval - elapsed
            if waited > 0:
                self._sleep(waited)
            self._last_call[domain] = self._clock()
            return waited


# The one shared instance every real outbound fetch must use - Rule 8.
default_limiter = SharedLimiter()
