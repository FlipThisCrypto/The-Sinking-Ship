# SPDX-License-Identifier: MIT
"""Alert if scuttle remaining is zero while confirmed backlog exists (safety)."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"engine"))
from fulfillment import SqliteLedger, PaymentState  # noqa: E402
from shipgen.config import GenConfig  # noqa: E402
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    cfg = GenConfig()
    budget = int(cfg.supply["public_mint_budget"])
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    led = SqliteLedger(args.db, caps)
    try:
        st = led.status_summary()
        conf = led.list_by_state(PaymentState.CONFIRMED)
    finally:
        led.close()
    rem = budget - int(st["supply_consumed"])
    danger = rem <= 0 and len(conf) > 0
    print(json.dumps({"budget_remaining": rem, "confirmed_backlog": len(conf), "danger": danger}))
    return 2 if danger else 0
if __name__ == "__main__":
    raise SystemExit(main())
