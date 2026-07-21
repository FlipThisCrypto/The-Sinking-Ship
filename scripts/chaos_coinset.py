# SPDX-License-Identifier: MIT
"""Failure-injection harness: coinset that fails N times then recovers.

Verifies daemon ticks remain fail-closed (no height advance, no fulfill)
while broken, then recover and fulfill when the source becomes healthy.

Usage:
    python scripts/chaos_coinset.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from fulfillment import (  # noqa: E402
    DryRunOfferBuilder,
    FulfillmentDaemon,
    SqliteLedger,
)
from fulfillment.types import PaymentSource, TierPurchase  # noqa: E402
from shipgen.config import GenConfig  # noqa: E402


class FlakySource(PaymentSource):
    def __init__(self, purchases: list[TierPurchase], fail_polls: int):
        self.purchases = purchases
        self.fail_polls = fail_polls
        self.polls = 0
        self.height = max(p.block_height for p in purchases)

    def poll_confirmed(self, since_height: int) -> list[TierPurchase]:
        self.polls += 1
        if self.polls <= self.fail_polls:
            raise RuntimeError(f"injected failure poll#{self.polls}")
        return [p for p in self.purchases if p.block_height >= since_height]

    def current_height(self) -> int:
        if self.polls < self.fail_polls:
            # height also flaky during outage
            raise RuntimeError("injected height failure")
        return self.height


def main() -> int:
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    coin = hashlib.sha256(b"chaos-coin").hexdigest()
    purchases = [
        TierPurchase(coin, "castaway", "txch1chaos", 99, "testnet11"),
    ]
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        led = SqliteLedger(work / "l.sqlite", caps)
        try:
            src = FlakySource(purchases, fail_polls=2)
            d = FulfillmentDaemon(
                source=src,
                ledger=led,
                offers=DryRunOfferBuilder(),
                salt=b"chaos-salt-NOT-MAINNET-00000001",
                cfg=cfg,
                manifest_outdir=work / "c",
                metadata_outdir=work / "m",
            )
            s1 = d.tick(dry_run=False)
            assert s1["errors"], "expected fail-closed errors"
            assert s1["fulfilled"] == 0
            h1 = led.last_polled_height()
            s2 = d.tick(dry_run=False)
            assert s2["errors"]
            assert led.last_polled_height() == h1  # no advance while failing
            s3 = d.tick(dry_run=False)
            assert not s3["errors"]
            assert s3["fulfilled"] == 1
            assert led.last_polled_height() == 99
            report = {
                "pass": True,
                "fail_polls": 2,
                "height_while_failed": h1,
                "final_height": led.last_polled_height(),
                "fulfilled": s3["fulfilled"],
            }
        finally:
            led.close()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
