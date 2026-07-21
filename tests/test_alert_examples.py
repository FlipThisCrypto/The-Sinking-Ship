# SPDX-License-Identifier: MIT
"""Fail CI if monitoring alert examples disappear."""
from pathlib import Path
def test_alert_examples_present():
    p = Path(__file__).resolve().parent.parent / "monitoring" / "alerts.promql.example"
    t = p.read_text(encoding="utf-8")
    assert "SinkingShipLedgerIntegrityFailed" in t
    assert "sinking_ship_budget_remaining" in t
