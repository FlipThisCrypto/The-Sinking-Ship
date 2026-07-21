# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fulfillment import DryRunOfferBuilder, FixturePaymentSource, FulfillmentDaemon, SqliteLedger
from shipgen.config import GenConfig

ROOT = Path(__file__).resolve().parent.parent
TEST_SALT = b"receipt-test-salt-NOT-MAINNET-001"


def test_export_buyer_receipt_script(tmp_path):
    import hashlib

    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    coin = hashlib.sha256(b"receipt-coin").hexdigest()
    fixture = tmp_path / "p.json"
    fixture.write_text(json.dumps([{
        "coin_id": coin,
        "tier_name": "castaway",
        "buyer_address": "txch1buyer",
        "block_height": 9,
        "network": "testnet11",
    }]), encoding="utf-8")
    db = tmp_path / "l.sqlite"
    led = SqliteLedger(db, caps)
    try:
        d = FulfillmentDaemon(
            source=FixturePaymentSource(fixture),
            ledger=led,
            offers=DryRunOfferBuilder(),
            salt=TEST_SALT,
            cfg=cfg,
            manifest_outdir=tmp_path / "c",
            metadata_outdir=tmp_path / "m",
        )
        assert d.tick(dry_run=False)["fulfilled"] == 1
    finally:
        led.close()

    out = tmp_path / "receipt.json"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_buyer_receipt.py"),
         "--db", str(db), "--coin-id", coin, "--out", str(out)],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["schema"] == "sinking-ship-buyer-receipt-v1"
    assert doc["state"] == "fulfilled"
    assert doc["manifest"]["manifest_hash"]
