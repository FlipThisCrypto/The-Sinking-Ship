# SPDX-License-Identifier: MIT
"""Tests for operational reporting and health CLI scripts."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from fulfillment import SqliteLedger
from fulfillment.types import TierPurchase

from shipgen.config import GenConfig

ROOT = Path(__file__).resolve().parent.parent


def test_export_refused_csv_script(tmp_path: Path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    db_path = tmp_path / "ledger.sqlite"
    csv_path = tmp_path / "refused.csv"

    ledger = SqliteLedger(db_path, caps)
    try:
        coin_id = "aa" * 32
        ledger.record_pending_hint(
            TierPurchase(
                coin_id=coin_id,
                tier_name="castaway",
                buyer_address="xch1refused",
                block_height=50,
                network="testnet11",
            )
        )
        ledger.mark_refused(coin_id, "budget_exceeded")

    finally:
        ledger.close()

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "export_refused_csv.py"),
        "--db",
        str(db_path),
        "--out",
        str(csv_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert csv_path.is_file()

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["coin_id"] == coin_id
        assert rows[0]["refuse_reason"] == "budget_exceeded"


def test_export_metrics_snapshot_script(tmp_path: Path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    db_path = tmp_path / "ledger.sqlite"
    jsonl_path = tmp_path / "metrics.jsonl"
    prom_path = tmp_path / "metrics.prom"

    ledger = SqliteLedger(db_path, caps)
    ledger.close()

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "export_metrics_snapshot.py"),
        "--db",
        str(db_path),
        "--out",
        str(jsonl_path),
        "--prom-out",
        str(prom_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert jsonl_path.is_file()
    assert prom_path.is_file()

    lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    doc = json.loads(lines[0])
    assert "health" in doc
    assert "status" in doc
    assert doc["health"]["level"] == "ok"

    prom_text = prom_path.read_text(encoding="utf-8")
    assert "sinking_ship_total_purchases" in prom_text


def test_cron_health_exit_script(tmp_path: Path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    db_path = tmp_path / "ledger.sqlite"

    ledger = SqliteLedger(db_path, caps)
    ledger.close()

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "cron_health_exit.py"),
        "--db",
        str(db_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    doc = json.loads(res.stdout)
    assert doc["level"] == "ok"
