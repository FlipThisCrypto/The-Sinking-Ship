# SPDX-License-Identifier: MIT
"""Stress: many fixture purchases in one tick (sequential engine, multi-chest)."""
from __future__ import annotations

import hashlib
import json

from fulfillment import (
    DryRunOfferBuilder,
    FixturePaymentSource,
    FulfillmentDaemon,
    PaymentState,
    SqliteLedger,
)
from shipgen.config import GenConfig


def test_twenty_castaways_one_tick(tmp_path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    rows = []
    for i in range(20):
        rows.append({
            "coin_id": hashlib.sha256(f"stress:{i}".encode()).hexdigest(),
            "tier_name": "castaway",
            "buyer_address": f"txch1buyer{i:04d}",
            "block_height": 100 + i,
            "network": "testnet11",
        })
    fixture = tmp_path / "many.json"
    fixture.write_text(json.dumps(rows), encoding="utf-8")
    ledger = SqliteLedger(tmp_path / "s.sqlite", caps)
    daemon = FulfillmentDaemon(
        source=FixturePaymentSource(fixture),
        ledger=ledger,
        offers=DryRunOfferBuilder(),
        salt=b"stress-tick-salt-NOT-MAINNET-0001",
        cfg=cfg,
        manifest_outdir=tmp_path / "chests",
        metadata_outdir=tmp_path / "meta",
    )
    s = daemon.tick(dry_run=False)
    assert s["fulfilled"] == 20
    assert not s["errors"]
    assert ledger.supply_consumed() == 20  # castaway qty always 1
    assert ledger.status_summary()["by_state"].get("fulfilled") == 20
    # all unique ordinals
    ordinals = set()
    for r in rows:
        st = ledger.state_of(r["coin_id"])
        assert st == PaymentState.FULFILLED
        ordinals.add(ledger.get_row(r["coin_id"])["pass_ordinal"])
    assert len(ordinals) == 20
    ledger.close()
