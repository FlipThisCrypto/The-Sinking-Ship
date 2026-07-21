# SPDX-License-Identifier: MIT
"""Canary tick: process at most N purchases then stop (blast-radius control).

Wraps a limited fixture slice so operators can dry-run production-like ticks
without draining a full backlog.

Usage:
    python scripts/canary_tick.py --fixture fixtures/example_payments.json \\
        --salt-file s.salt --db out/c.sqlite --max-purchases 1
"""
from __future__ import annotations

import argparse
import json
import sys
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
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--salt-file", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--max-purchases", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    raw = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print(json.dumps({"error": "fixture must be array"}))
        return 1
    limited = raw[: max(0, args.max_purchases)]
    work = Path(args.db).parent
    work.mkdir(parents=True, exist_ok=True)
    slim = work / "canary_fixture.json"
    slim.write_text(json.dumps(limited), encoding="utf-8")

    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    led = SqliteLedger(args.db, caps)
    try:
        d = FulfillmentDaemon(
            source=FixturePaymentSource(slim),
            ledger=led,
            offers=DryRunOfferBuilder(),
            salt=Path(args.salt_file).read_bytes().strip(),
            cfg=cfg,
            manifest_outdir=work / "canary_chests",
            metadata_outdir=work / "canary_meta",
        )
        summary = d.tick(dry_run=args.dry_run)
        summary["canary_max"] = args.max_purchases
        summary["canary_input"] = len(limited)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1 if summary.get("errors") else 0
    finally:
        led.close()


if __name__ == "__main__":
    sys.exit(main())
