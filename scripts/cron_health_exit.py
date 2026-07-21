# SPDX-License-Identifier: MIT
"""Count open severity of ledger health for simple exit codes in cron."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"engine"))
from fulfillment import SqliteLedger, build_health  # noqa: E402
from shipgen.config import GenConfig  # noqa: E402
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    led = SqliteLedger(args.db, caps)
    try:
        st = led.status_summary()
    finally:
        led.close()
    budget = int(cfg.supply["public_mint_budget"])
    st["public_mint_budget"] = budget
    st["budget_remaining"] = max(0, budget - int(st["supply_consumed"]))
    h = build_health(status=st, public_mint_budget=budget)
    print(json.dumps(h, indent=2, sort_keys=True))
    return {"ok": 0, "degraded": 1, "critical": 2}[h["level"]]
if __name__ == "__main__":
    raise SystemExit(main())
