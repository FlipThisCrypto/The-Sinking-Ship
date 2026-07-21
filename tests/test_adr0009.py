# SPDX-License-Identifier: MIT
from pathlib import Path
def test_adr0009_exists():
    p = Path(__file__).resolve().parent.parent / "docs" / "adr" / "ADR-0009-circuit-breaker-and-reconcile-lock.md"
    assert p.is_file()
    assert "CircuitBreaker" in p.read_text(encoding="utf-8")
