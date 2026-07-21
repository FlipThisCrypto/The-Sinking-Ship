# SPDX-License-Identifier: MIT
"""Project supply and revenue under partial sellout scenarios.

Strategic planning: estimate remaining budget, revenue, and Torn realization
when only a fraction of each tier sells (stress for scuttling messaging).

Usage:
    python scripts/project_partial_sellout.py --fraction 0.4
    python scripts/project_partial_sellout.py --fraction 0.1 --json-out out.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from shipgen.config import GenConfig  # noqa: E402


def project(fraction: float) -> dict:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be in [0, 1]")
    cfg = GenConfig()
    budget = int(cfg.supply["public_mint_budget"])
    rows = []
    revenue = 0.0
    expected_supply = 0.0
    for t in cfg.tiers_doc["tiers"]:
        passes = int(t["passes"] * fraction)
        exp_supply = float(t["expected_supply"]) * fraction
        price = t.get("price_xch")
        rev = float(price) * passes if price is not None else 0.0
        revenue += rev
        expected_supply += exp_supply
        rows.append({
            "tier": t["name"],
            "passes_sold": passes,
            "expected_supply": round(exp_supply, 2),
            "revenue_xch": round(rev, 4),
        })
    return {
        "schema": "sinking-ship-partial-sellout-v1",
        "fraction": fraction,
        "public_mint_budget": budget,
        "projected_supply": round(expected_supply, 2),
        "projected_revenue_xch": round(revenue, 4),
        "budget_headroom": round(budget - expected_supply, 2),
        "tiers": rows,
        "scuttling_note": (
            "Unsold public capacity is destroyed at window close; "
            "realized supply is lower than cap under partial sellout."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fraction", type=float, default=0.5)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    try:
        report = project(args.fraction)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        return 1
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
