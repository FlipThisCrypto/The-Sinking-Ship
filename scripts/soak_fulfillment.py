# SPDX-License-Identifier: MIT
"""Concurrent-style soak: many confirmed purchases through one ledger.

Simulates a burst of payments with unique coin ids, ticks the daemon, and
reports throughput + refusal/error counts. Offline only (fixture source).

Usage:
    python scripts/soak_fulfillment.py --purchases 50
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from fulfillment import (  # noqa: E402
    DryRunOfferBuilder,
    FixturePaymentSource,
    FulfillmentDaemon,
    SqliteLedger,
)
from shipgen.config import GenConfig  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--purchases", type=int, default=50)
    ap.add_argument("--tier", default="castaway")
    ap.add_argument("--workdir", default="output/fulfillment/soak")
    args = ap.parse_args()

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    salt = work / "soak.salt"
    if not salt.exists():
        salt.write_bytes(b"soak-test-salt-NOT-MAINNET-0001")

    rows = []
    for i in range(args.purchases):
        coin = hashlib.sha256(f"soak:{i}".encode()).hexdigest()
        rows.append({
            "coin_id": coin,
            "tier_name": args.tier,
            "buyer_address": f"txch1soak{i:04d}",
            "block_height": 1000 + i,
            "network": "testnet11",
        })
    fixture = work / "purchases.json"
    fixture.write_text(json.dumps(rows), encoding="utf-8")

    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    # Cap soak to tier pass budget so we measure fulfill, not mass refusal.
    max_passes = caps.get(args.tier, args.purchases)
    if args.purchases > max_passes:
        rows = rows[:max_passes]
        fixture.write_text(json.dumps(rows), encoding="utf-8")
        print(json.dumps({
            "note": f"truncated to {max_passes} purchases (tier pass cap)",
            "requested": args.purchases,
        }))

    db = work / "ledger.sqlite"
    if db.exists():
        db.unlink()
    ledger = SqliteLedger(db, caps)
    try:
        daemon = FulfillmentDaemon(
            source=FixturePaymentSource(fixture),
            ledger=ledger,
            offers=DryRunOfferBuilder(),
            salt=salt.read_bytes().strip(),
            cfg=cfg,
            manifest_outdir=work / "chests",
            metadata_outdir=work / "meta",
            reveal_outdir=work / "reveal",
        )
        t0 = time.perf_counter()
        summary = daemon.tick(dry_run=False)
        wall = time.perf_counter() - t0
        status = ledger.status_summary()
    finally:
        ledger.close()

    n = len(rows)
    report = {
        "purchases": n,
        "wall_s": round(wall, 4),
        "per_purchase_ms": round((wall / max(1, n)) * 1000, 3),
        "tick": summary,
        "status": status,
        "pass": (
            summary.get("fulfilled", 0) == n
            and not summary.get("errors")
            and status.get("integrity_ok")
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    (work / "soak_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
