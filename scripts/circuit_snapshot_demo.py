# SPDX-License-Identifier: MIT
"""Emit circuit breaker snapshot as JSON for health enrichment."""
from __future__ import annotations
import json
from fulfillment.circuit_breaker import CircuitBreaker
def demo():
    b = CircuitBreaker(failure_threshold=5, open_seconds=30)
    return b.snapshot()
if __name__ == "__main__":
    print(json.dumps(demo()))
