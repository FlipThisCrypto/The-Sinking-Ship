# SPDX-License-Identifier: MIT
"""List refused purchases as CSV for support ticket import."""
from __future__ import annotations
import argparse
import csv
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"engine"))
from fulfillment import SqliteLedger  # noqa: E402
from shipgen.config import GenConfig  # noqa: E402
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    led = SqliteLedger(args.db, caps)
    try:
        rows = led.list_refused()
    finally:
        led.close()
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["coin_id","tier_name","pass_ordinal","buyer_address","block_height","refuse_reason","updated_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(json.dumps({"ok": True, "rows": len(rows), "out": str(path)}))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
