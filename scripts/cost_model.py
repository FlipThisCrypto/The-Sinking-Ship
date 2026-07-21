# SPDX-License-Identifier: MIT
"""Rough ops cost model for mint-window hosting (strategic planning).

Not a quote — order-of-magnitude inputs for XCH revenue vs infra spend.

Usage:
    python scripts/cost_model.py --days 14 --rpc-usd-per-day 5 --host-usd-per-day 2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from shipgen.config import GenConfig  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--rpc-usd-per-day", type=float, default=5.0)
    ap.add_argument("--host-usd-per-day", type=float, default=2.0)
    ap.add_argument("--xch-usd", type=float, default=20.0, help="spot assumption")
    ap.add_argument("--sellout-fraction", type=float, default=1.0)
    args = ap.parse_args()

    cfg = GenConfig()
    revenue_xch = 0.0
    for t in cfg.tiers_doc["tiers"]:
        if t.get("price_xch") is None:
            continue
        revenue_xch += float(t["price_xch"]) * int(t["passes"]) * args.sellout_fraction

    infra = (args.rpc_usd_per_day + args.host_usd_per_day) * args.days
    revenue_usd = revenue_xch * args.xch_usd
    report = {
        "schema": "sinking-ship-cost-model-v1",
        "assumptions": {
            "days": args.days,
            "rpc_usd_per_day": args.rpc_usd_per_day,
            "host_usd_per_day": args.host_usd_per_day,
            "xch_usd": args.xch_usd,
            "sellout_fraction": args.sellout_fraction,
        },
        "projected_revenue_xch": round(revenue_xch, 4),
        "projected_revenue_usd": round(revenue_usd, 2),
        "infra_usd": round(infra, 2),
        "infra_as_pct_of_revenue": (
            round(100.0 * infra / revenue_usd, 4) if revenue_usd else None
        ),
        "note": "Illustrative only; exclude art, legal, marketing, royalties.",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
