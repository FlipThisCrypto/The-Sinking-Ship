# SPDX-License-Identifier: MIT
from fulfillment.budget_guard import can_accept_chest, utilization


def test_can_accept_chest_matrix():
    assert can_accept_chest(10, 3) == (True, None)
    ok, reason = can_accept_chest(0, 1)
    assert ok is False and "exhausted" in reason
    ok, reason = can_accept_chest(5, 6)
    assert ok is False and "exceed" in reason
    ok, reason = can_accept_chest(5, 0)
    assert ok is False and "invalid" in reason


def test_utilization_bounds():
    assert utilization(0, 100) == 0.0
    assert utilization(50, 100) == 0.5
    assert utilization(100, 100) == 1.0
    assert utilization(120, 100) == 1.0
