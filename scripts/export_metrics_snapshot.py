# SPDX-License-Identifier: MIT
"""Periodic metrics snapshot writer for hosts without Prometheus.

Appends a JSONL line with health + status each run — cheap historical trail.

Usage:
    python scripts/export_metrics_snapshot.py --db ledger.sqlite --out metrics.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from fulfillment import SqliteLedger, build_health  # noqa: E402
from fulfillment.metrics import status_to_prometheus  # noqa: E402
from shipgen.config import GenConfig  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True, help="JSONL append path")
    ap.add_argument("--prom-out", default=None, help="optional overwrite .prom file")
    args = ap.parse_args()

    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    budget = int(cfg.supply["public_mint_budget"])
    led = SqliteLedger(args.db, caps)
    try:
        st = led.status_summary()
    finally:
        led.close()
    st["public_mint_budget"] = budget
    st["budget_remaining"] = max(0, budget - int(st["supply_consumed"]))
    health = build_health(status=st, public_mint_budget=budget)
    line = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "health": health,
        "status": st,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(line, sort_keys=True) + "\n")
    if args.prom_out:
        Path(args.prom_out).write_text(
            status_to_prometheus(st), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": True, "level": health["level"], "out": str(out)}))
    return 0 if health["level"] != "critical" else 2


if __name__ == "__main__":
    sys.exit(main())
