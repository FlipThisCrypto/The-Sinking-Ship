# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from fulfillment.circuit_breaker import CircuitBreaker
from fulfillment.sources import CoinsetPollingSource


def test_breaker_opens_after_threshold():
    b = CircuitBreaker(failure_threshold=3, open_seconds=60.0)
    assert b.allow()
    for _ in range(3):
        b.record_failure()
    assert b.state == "open"
    assert b.allow() is False


def test_breaker_closes_on_success():
    b = CircuitBreaker(failure_threshold=2, open_seconds=60.0)
    b.record_failure()
    b.record_failure()
    assert b.state == "open"
    b.state = "half_open"
    b.record_success()
    assert b.state == "closed"
    assert b.allow()


def test_coinset_respects_open_circuit():
    b = CircuitBreaker(failure_threshold=1, open_seconds=60.0)
    b.record_failure()
    assert b.state == "open"

    def http_get(url: str) -> bytes:
        raise AssertionError("should not call HTTP when open")

    src = CoinsetPollingSource("http://x", http_get=http_get, circuit_breaker=b)
    with pytest.raises(RuntimeError, match="circuit"):
        src.current_height()
