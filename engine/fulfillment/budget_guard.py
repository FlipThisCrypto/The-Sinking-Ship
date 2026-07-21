# SPDX-License-Identifier: MIT
"""Pure helpers for public-mint budget decisions (unit-testable)."""
from __future__ import annotations


def can_accept_chest(remaining: int, quantity: int) -> tuple[bool, str | None]:
    """Return (ok, refuse_reason). quantity must be positive when ok path."""
    if remaining <= 0:
        return False, f"public mint budget exhausted (remaining={remaining})"
    if quantity < 1:
        return False, f"invalid chest quantity {quantity}"
    if quantity > remaining:
        return False, (
            f"chest qty {quantity} would exceed budget remaining={remaining}"
        )
    return True, None


def utilization(consumed: int, budget: int) -> float:
    if budget <= 0:
        return 1.0
    return min(1.0, max(0.0, consumed / budget))
