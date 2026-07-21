# SPDX-License-Identifier: MIT
"""Circuit breaker for fail-closed payment sources under flapping RPCs.

After N consecutive transport failures, opens for a cool-down so operators
and monitors see a stable degraded state instead of thrashing every tick.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    open_seconds: float = 30.0
    _failures: int = 0
    _opened_at: float | None = None
    state: str = "closed"  # closed | open | half_open

    def allow(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if self._opened_at is None:
                return False
            if time.monotonic() - self._opened_at >= self.open_seconds:
                self.state = "half_open"
                return True
            return False
        # half_open: allow one probe
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self.state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        if self.state == "half_open" or self._failures >= self.failure_threshold:
            self.state = "open"
            self._opened_at = time.monotonic()

    def snapshot(self) -> dict:
        return {
            "state": self.state,
            "failures": self._failures,
            "failure_threshold": self.failure_threshold,
            "open_seconds": self.open_seconds,
        }
