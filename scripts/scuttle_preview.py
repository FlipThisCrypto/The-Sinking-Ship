# SPDX-License-Identifier: MIT
"""Simulate scuttling remaining budget (numbers only; no chain)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"engine"))
from fulfillment import SqliteLedger
from shipgen.config import GenConfig
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    cfg = GenConfig()
    budget = int(cfg.supply["public_mint_budget"])
    cap = int(cfg.supply["cap"])
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    led = SqliteLedger(args.db, caps)
    try:
        st = led.status_summary()
    finally:
        led.close()
    consumed = int(st["supply_consumed"])
    scuttle = max(0, budget - consumed)
    print(json.dumps({
        "schema": "sinking-ship-scuttle-preview-v1",
        "supply_cap": cap,
        "public_mint_budget": budget,
        "supply_consumed": consumed,
        "unminted_public_to_scuttle": scuttle,
        "note": "Ceremony still follows docs/SCUTTLING-PROCEDURE.md on-chain steps.",
    }, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
