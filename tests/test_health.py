# SPDX-License-Identifier: MIT
from fulfillment.health import build_health


def test_health_ok_when_integrity_and_headroom():
    h = build_health(
        status={
            "integrity_ok": True,
            "supply_consumed": 100,
            "by_state": {"fulfilled": 10},
        },
        public_mint_budget=44000,
    )
    assert h["level"] == "ok"
    assert h["ok"] is True
    assert h["budget_remaining"] == 43900


def test_health_critical_on_integrity_fail():
    h = build_health(
        status={"integrity_ok": False, "supply_consumed": 0, "by_state": {}},
        public_mint_budget=44000,
    )
    assert h["level"] == "critical"
    assert "ledger_integrity_failed" in h["reasons"]


def test_health_critical_budget_exhausted_with_backlog():
    h = build_health(
        status={
            "integrity_ok": True,
            "supply_consumed": 44000,
            "by_state": {"confirmed": 3},
        },
        public_mint_budget=44000,
    )
    assert h["level"] == "critical"
    assert "budget_exhausted_with_backlog" in h["reasons"]
