# SPDX-License-Identifier: MIT
"""Tests for fulfillment types and state machine enums (engine/fulfillment/types.py)."""
from __future__ import annotations

import pytest

from fulfillment.types import PaymentState, TierPurchase


def test_payment_state_values():
    assert PaymentState.DISPENSED == "dispensed"
    assert PaymentState.PENDING == "pending"
    assert PaymentState.CONFIRMED == "confirmed"
    assert PaymentState.ROLLED == "rolled"
    assert PaymentState.EXPIRED == "expired"
    assert PaymentState.FULFILLED == "fulfilled"
    assert PaymentState.REFUSED == "refused"


def test_tier_purchase_dataclass_immutable():
    p = TierPurchase(
        coin_id="a" * 64,
        tier_name="castaway",
        buyer_address="xch1buyer",
        block_height=12345,
        network="testnet11",
    )
    assert p.coin_id == "a" * 64
    assert p.tier_name == "castaway"

    with pytest.raises(AttributeError):
        p.tier_name = "admiral"  # dataclass is frozen
