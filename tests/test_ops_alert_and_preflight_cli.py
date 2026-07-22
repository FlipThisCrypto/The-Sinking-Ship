# SPDX-License-Identifier: MIT
"""Tests for canary tick, budget backlog alert, and go/no-go report CLI scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fulfillment import SqliteLedger
from fulfillment.types import TierPurchase
from shipgen.config import GenConfig

ROOT = Path(__file__).resolve().parent.parent


def test_alert_budget_backlog_script(tmp_path: Path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    db_path = tmp_path / "ledger.sqlite"

    ledger = SqliteLedger(db_path, caps)
    try:
        ledger.record_purchase(
            TierPurchase(
                coin_id="33" * 32,
                tier_name="castaway",
                buyer_address="xch1test",
                block_height=10,
                network="testnet11",
            )
        )
    finally:
        ledger.close()

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "alert_budget_backlog.py"),
        "--db",
        str(db_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    doc = json.loads(res.stdout)
    assert doc["danger"] is False
    assert doc["confirmed_backlog"] == 1


def test_canary_tick_script(tmp_path: Path):
    db_path = tmp_path / "canary.sqlite"
    salt_file = tmp_path / "test.salt"
    salt_file.write_bytes(b"canary-test-salt-16bytes-min")
    fixture = tmp_path / "fixture.json"

    items = [
        {
            "coin_id": "44" * 32,
            "tier_name": "castaway",
            "buyer_address": "xch1canary1",
            "block_height": 1,
            "network": "testnet11",
        },
        {
            "coin_id": "55" * 32,
            "tier_name": "castaway",
            "buyer_address": "xch1canary2",
            "block_height": 2,
            "network": "testnet11",
        },
    ]
    fixture.write_text(json.dumps(items), encoding="utf-8")

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "canary_tick.py"),
        "--fixture",
        str(fixture),
        "--salt-file",
        str(salt_file),
        "--db",
        str(db_path),
        "--max-purchases",
        "1",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    doc = json.loads(res.stdout)
    assert doc["canary_max"] == 1
    assert doc["canary_input"] == 1
    assert doc["fulfilled"] == 1



def test_gen_gonogo_report_script(tmp_path: Path):
    salt_file = tmp_path / "test.salt"
    salt_file.write_bytes(b"gonogo-test-salt-16bytes-min")
    report_file = tmp_path / "gonogo.md"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "gen_gonogo_report.py"),
        "--salt-file",
        str(salt_file),
        "--out",
        str(report_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert report_file.is_file()
    text = report_file.read_text(encoding="utf-8")
    assert "# Mint go/no-go" in text
    assert "Preflight ok:" in text
