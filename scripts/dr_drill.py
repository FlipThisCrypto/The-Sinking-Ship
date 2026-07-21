# SPDX-License-Identifier: MIT
"""Disaster-recovery drill: backup ledger, wipe primary path, restore, verify.

Offline fixture-based. Proves backup → restore → status integrity without
touching production paths when run against a temp workdir.

Usage:
    python scripts/dr_drill.py --workdir output/dr_drill
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
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
    ap.add_argument("--workdir", default="output/dr_drill")
    args = ap.parse_args()
    work = Path(args.workdir)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    salt = work / "drill.salt"
    salt.write_bytes(b"dr-drill-salt-NOT-MAINNET-000001")
    coin = hashlib.sha256(b"dr-drill-coin").hexdigest()
    fixture = work / "pay.json"
    fixture.write_text(json.dumps([{
        "coin_id": coin,
        "tier_name": "castaway",
        "buyer_address": "txch1drdrill",
        "block_height": 42,
        "network": "testnet11",
    }]), encoding="utf-8")

    primary = work / "ledger.sqlite"
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    led = SqliteLedger(primary, caps)
    try:
        d = FulfillmentDaemon(
            source=FixturePaymentSource(fixture),
            ledger=led,
            offers=DryRunOfferBuilder(),
            salt=salt.read_bytes(),
            cfg=cfg,
            manifest_outdir=work / "chests",
            metadata_outdir=work / "meta",
        )
        summary = d.tick(dry_run=False)
        assert summary["fulfilled"] == 1
        before = led.status_summary()
    finally:
        led.close()

    backup = work / "backup.sqlite"
    r = subprocess.run(
        [sys.executable, str(ROOT / "engine" / "fulfillment_daemon.py"),
         "backup", "--db", str(primary), "--out", str(backup)],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        print(r.stderr)
        return 1

    # Simulate primary loss
    primary.unlink()
    shutil.copy2(backup, primary)

    led2 = SqliteLedger(primary, caps)
    try:
        after = led2.status_summary()
        row = led2.get_row(coin)
    finally:
        led2.close()

    report = {
        "schema": "sinking-ship-dr-drill-v1",
        "pass": (
            after.get("integrity_ok") is True
            and after.get("total_purchases") == before.get("total_purchases")
            and row is not None
            and row.get("state") == "fulfilled"
        ),
        "before": before,
        "after": after,
        "restored_coin_state": row.get("state") if row else None,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    (work / "dr_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
