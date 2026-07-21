# SPDX-License-Identifier: MIT
"""Cross-check ledger supply vs config public mint budget (ops report).

Usage:
    python scripts/reconcile_budget_report.py --db output/fulfillment/ledger.sqlite
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from fulfillment import SqliteLedger  # noqa: E402
from shipgen.config import GenConfig  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    args = ap.parse_args()

    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    budget = int(cfg.supply["public_mint_budget"])
    cap = int(cfg.supply["cap"])
    reserve = int(cfg.supply.get("treasury_reserve", cfg.supply.get("reserve", 0)))

    led = SqliteLedger(args.db, caps)
    try:
        st = led.status_summary()
    finally:
        led.close()

    consumed = int(st["supply_consumed"])
    remaining = max(0, budget - consumed)
    report = {
        "schema": "sinking-ship-budget-report-v1",
        "config_hash": cfg.config_hash,
        "supply_cap": cap,
        "treasury_reserve": reserve,
        "public_mint_budget": budget,
        "supply_consumed": consumed,
        "budget_remaining": remaining,
        "budget_utilization": round(consumed / budget, 6) if budget else None,
        "ledger": st,
        "alert": remaining == 0,
        "ok": st.get("integrity_ok", False) and consumed <= budget,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
