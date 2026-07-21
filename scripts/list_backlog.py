# SPDX-License-Identifier: MIT
"""Detect orphan rolled-but-not-fulfilled purchases for resume ops."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"engine"))
from fulfillment import SqliteLedger, PaymentState
from shipgen.config import GenConfig
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    led = SqliteLedger(args.db, caps)
    try:
        rows = led.list_by_state(PaymentState.ROLLED)
        conf = led.list_by_state(PaymentState.CONFIRMED)
    finally:
        led.close()
    print(json.dumps({
        "rolled_backlog": len(rows),
        "confirmed_backlog": len(conf),
        "needs_tick": len(rows)+len(conf) > 0,
        "rolled_coin_ids": [r["coin_id"] for r in rows[:20]],
    }, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
