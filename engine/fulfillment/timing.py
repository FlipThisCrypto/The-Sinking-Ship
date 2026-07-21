# SPDX-License-Identifier: MIT
"""Soft max tick duration warning for ops (does not fail tick)."""
from __future__ import annotations
import time
from contextlib import contextmanager
@contextmanager
def timed_section(name: str, warn_ms: float = 5000.0):
    t0 = time.perf_counter()
    yield
    ms = (time.perf_counter() - t0) * 1000
    if ms > warn_ms:
        print(f"WARN slow_section {name} {ms:.1f}ms > {warn_ms}ms")
