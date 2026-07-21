# SPDX-License-Identifier: MIT
"""Render fulfillment ledger status as Prometheus text exposition format.

Enables scrape-friendly monitoring without embedding a metrics server.
Operators can `curl` a file written by the CLI or pipe `status --metrics`.
"""
from __future__ import annotations

from typing import Any


def status_to_prometheus(status: dict[str, Any], *, job: str = "sinking_ship_fulfillment") -> str:
    """Convert SqliteLedger.status_summary() (+ optional tick fields) to text."""
    lines: list[str] = [
        f'# HELP sinking_ship_fulfillment_info Static labels for the fulfillment job.',
        f'# TYPE sinking_ship_fulfillment_info gauge',
        f'sinking_ship_fulfillment_info{{job="{_esc(job)}"}} 1',
    ]
    by_state = status.get("by_state") or {}
    lines.append("# HELP sinking_ship_purchases_by_state Purchase rows by ledger state")
    lines.append("# TYPE sinking_ship_purchases_by_state gauge")
    for state, n in sorted(by_state.items()):
        lines.append(
            f'sinking_ship_purchases_by_state{{state="{_esc(state)}"}} {int(n)}'
        )
    # Always emit known states at 0 when missing for stable dashboards.
    for state in ("pending", "confirmed", "rolled", "fulfilled", "refused"):
        if state not in by_state:
            lines.append(f'sinking_ship_purchases_by_state{{state="{state}"}} 0')

    budget = status.get("public_mint_budget")
    consumed = int(status.get("supply_consumed", 0))
    remaining = status.get("budget_remaining")
    if remaining is None and budget is not None:
        remaining = max(0, int(budget) - consumed)
    gauges = [
        ("sinking_ship_supply_consumed", "NFTs counted against public mint budget",
         consumed),
        ("sinking_ship_public_mint_budget", "Configured public mint budget",
         int(budget) if budget is not None else 0),
        ("sinking_ship_budget_remaining", "Budget headroom (NFTs)",
         int(remaining) if remaining is not None else 0),
        ("sinking_ship_next_start_index", "Next global index for generated NFTs",
         status.get("next_start_index", 0)),
        ("sinking_ship_last_polled_height", "Last successfully polled chain height",
         status.get("last_polled_height", 0)),
        ("sinking_ship_total_purchases", "Total purchase rows in the ledger",
         status.get("total_purchases", 0)),
        ("sinking_ship_ledger_integrity_ok", "1 if PRAGMA quick_check is ok",
         1 if status.get("integrity_ok") else 0),
    ]
    for name, help_text, value in gauges:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {int(value)}")
    return "\n".join(lines) + "\n"


def _esc(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
