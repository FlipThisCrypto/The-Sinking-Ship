# SPDX-License-Identifier: MIT
"""Composite health document for fulfillment ops (local file or future HTTP)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_health(
    *,
    status: dict[str, Any],
    public_mint_budget: int | None = None,
    network: str = "testnet11",
) -> dict[str, Any]:
    consumed = int(status.get("supply_consumed", 0))
    integrity = bool(status.get("integrity_ok"))
    budget = public_mint_budget
    remaining = None
    if budget is not None:
        remaining = max(0, int(budget) - consumed)
    # Degraded if integrity fails or budget exhausted with pending work.
    by_state = status.get("by_state") or {}
    pending_work = int(by_state.get("confirmed", 0)) + int(by_state.get("rolled", 0))
    level = "ok"
    reasons: list[str] = []
    if not integrity:
        level = "critical"
        reasons.append("ledger_integrity_failed")
    elif budget is not None and remaining == 0 and pending_work > 0:
        level = "critical"
        reasons.append("budget_exhausted_with_backlog")
    elif budget is not None and remaining is not None and remaining < max(10, int(budget) * 0.01):
        level = "degraded"
        reasons.append("budget_low")
    elif pending_work > 50:
        level = "degraded"
        reasons.append("fulfillment_backlog")
    return {
        "schema": "sinking-ship-health-v1",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "network": network,
        "level": level,
        "ok": level == "ok",
        "reasons": reasons,
        "status": status,
        "public_mint_budget": budget,
        "budget_remaining": remaining,
    }
