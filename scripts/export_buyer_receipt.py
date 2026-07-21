# SPDX-License-Identifier: MIT
"""Export a human-readable buyer receipt from a ledger row + chest manifest.

Usage:
    python scripts/export_buyer_receipt.py --db ledger.sqlite --coin-id <hex> --out receipt.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from fulfillment import SqliteLedger  # noqa: E402
from shipgen.config import GenConfig  # noqa: E402
from shipgen.drbg import normalize_coin_id  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--coin-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest-dir", default=None,
                    help="optional directory of chest_*.json to attach")
    args = ap.parse_args()

    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    coin = normalize_coin_id(args.coin_id)
    led = SqliteLedger(args.db, caps)
    try:
        row = led.get_row(coin)
        if row is None:
            print(json.dumps({"error": "not found", "coin_id": coin}))
            return 1
        manifest = led.get_manifest(coin)
        receipt = {
            "schema": "sinking-ship-buyer-receipt-v1",
            "coin_id": coin,
            "state": row["state"],
            "tier_name": row["tier_name"],
            "pass_ordinal": row["pass_ordinal"],
            "buyer_address": row["buyer_address"],
            "block_height": row["block_height"],
            "network": row["network"],
            "quantity": row.get("quantity"),
            "manifest_hash": row.get("manifest_hash"),
            "offer_id": row.get("offer_id"),
            "refuse_reason": row.get("refuse_reason"),
            "updated_at": row.get("updated_at"),
            "manifest": manifest,
            "verify_hint": (
                "After salt reveal: python engine/chest_roller.py verify "
                "--manifest <chest.json> --salt-file <revealed.salt>"
            ),
        }
    finally:
        led.close()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"ok": True, "out": args.out, "state": receipt["state"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
