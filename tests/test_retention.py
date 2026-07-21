# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fulfillment.ledger import SqliteLedger
from fulfillment.retention import archive_fulfilled
from fulfillment.types import PaymentState, TierPurchase
from shipgen.config import GenConfig
from shipgen.drbg import normalize_coin_id


def test_archive_fulfilled_dry_run_and_apply(tmp_path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    db = tmp_path / "l.sqlite"
    led = SqliteLedger(db, caps)
    coin = normalize_coin_id("ab" * 32)
    led.record_purchase(TierPurchase(coin, "castaway", "txch1a", 1, "testnet11"))
    # Force fulfilled + old timestamp
    old = (datetime.now(timezone.utc) - timedelta(days=40)).replace(microsecond=0).isoformat()
    led._conn.execute(
        "UPDATE purchases SET state = ?, updated_at = ?, manifest_hash = ? WHERE coin_id = ?",
        (PaymentState.FULFILLED.value, old, "h" * 64, coin),
    )
    led.close()

    arch = tmp_path / "arch.json"
    dry = archive_fulfilled(db, older_than_days=30, archive_path=arch, dry_run=True)
    assert dry["matched"] == 1
    assert dry["deleted"] == 0
    assert not arch.exists()

    applied = archive_fulfilled(db, older_than_days=30, archive_path=arch, dry_run=False)
    assert applied["deleted"] == 1
    docs = json.loads(arch.read_text(encoding="utf-8"))
    assert len(docs) == 1
    assert docs[0]["coin_id"] == coin

    led2 = SqliteLedger(db, caps)
    try:
        assert led2.get_row(coin) is None
        assert led2.status_summary()["total_purchases"] == 0
    finally:
        led2.close()
