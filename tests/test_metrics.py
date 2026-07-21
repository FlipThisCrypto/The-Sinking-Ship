# SPDX-License-Identifier: MIT
from fulfillment.metrics import status_to_prometheus


def test_prometheus_export_contains_core_gauges():
    text = status_to_prometheus({
        "by_state": {"fulfilled": 3, "refused": 1},
        "supply_consumed": 13,
        "next_start_index": 14,
        "last_polled_height": 102,
        "total_purchases": 4,
        "integrity_ok": True,
    })
    assert "sinking_ship_purchases_by_state{state=\"fulfilled\"} 3" in text
    assert "sinking_ship_purchases_by_state{state=\"pending\"} 0" in text
    assert "sinking_ship_supply_consumed 13" in text
    assert "sinking_ship_ledger_integrity_ok 1" in text
    assert text.endswith("\n")
