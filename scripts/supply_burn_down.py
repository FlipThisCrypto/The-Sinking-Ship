# SPDX-License-Identifier: MIT
"""Estimate days-to-exhaustion of public mint budget given recent burn rate.

Reads metrics JSONL snapshots (export_metrics_snapshot) or takes manual
consumed_now / consumed_then samples.

Usage:
    python scripts/supply_burn_down.py --jsonl metrics.jsonl
    python scripts/supply_burn_down.py --consumed-then 1000 --consumed-now 2500 --hours 24
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
    ap.add_argument("--jsonl", default=None)
    ap.add_argument("--consumed-then", type=int, default=None)
    ap.add_argument("--consumed-now", type=int, default=None)
    ap.add_argument("--hours", type=float, default=None)
    args = ap.parse_args()

    budget = int(GenConfig().supply["public_mint_budget"])
    if args.jsonl:
        lines = Path(args.jsonl).read_text(encoding="utf-8").strip().splitlines()
        if len(lines) < 2:
            print(json.dumps({"error": "need >=2 jsonl samples"}))
            return 1
        a = json.loads(lines[0])
        b = json.loads(lines[-1])
        c0 = int(a["status"]["supply_consumed"])
        c1 = int(b["status"]["supply_consumed"])
        # Assume equal spacing unknown; use sample count as relative hours if not parseable
        hours = max(1.0, float(len(lines) - 1))
    else:
        if args.consumed_then is None or args.consumed_now is None or args.hours is None:
            print(json.dumps({"error": "provide --jsonl or then/now/hours"}))
            return 1
        c0, c1, hours = args.consumed_then, args.consumed_now, float(args.hours)

    delta = c1 - c0
    rate = delta / hours if hours else 0.0
    remaining = max(0, budget - c1)
    hours_left = (remaining / rate) if rate > 0 else None
    report = {
        "schema": "sinking-ship-burn-down-v1",
        "budget": budget,
        "consumed": c1,
        "remaining": remaining,
        "delta": delta,
        "hours_window": hours,
        "nfts_per_hour": round(rate, 4),
        "est_hours_to_exhaustion": (
            round(hours_left, 2) if hours_left is not None else None
        ),
        "alert": hours_left is not None and hours_left < 24,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
