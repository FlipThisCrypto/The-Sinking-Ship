# SPDX-License-Identifier: MIT
"""Emit circuit breaker snapshot as JSON for health enrichment."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from fulfillment.circuit_breaker import CircuitBreaker  # noqa: E402

def demo():
    b = CircuitBreaker(failure_threshold=5, open_seconds=30)
    return b.snapshot()
if __name__ == "__main__":
    print(json.dumps(demo()))
