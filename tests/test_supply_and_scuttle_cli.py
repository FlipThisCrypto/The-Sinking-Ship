# SPDX-License-Identifier: MIT
"""Tests for supply metrics, burn-down, and scuttle preview CLI scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fulfillment import SqliteLedger
from shipgen.config import GenConfig

ROOT = Path(__file__).resolve().parent.parent


def test_scuttle_preview_script(tmp_path: Path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    db_path = tmp_path / "ledger.sqlite"

    ledger = SqliteLedger(db_path, caps)
    ledger.close()

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "scuttle_preview.py"),
        "--db",
        str(db_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    doc = json.loads(res.stdout)
    assert doc["schema"] == "sinking-ship-scuttle-preview-v1"
    assert doc["public_mint_budget"] == int(cfg.supply["public_mint_budget"])
    assert doc["unminted_public_to_scuttle"] == int(cfg.supply["public_mint_budget"])


def test_supply_burn_down_script(tmp_path: Path):
    # 1. Manual parameters
    cmd_manual = [
        sys.executable,
        str(ROOT / "scripts" / "supply_burn_down.py"),
        "--consumed-then",
        "1000",
        "--consumed-now",
        "2000",
        "--hours",
        "10",
    ]
    res = subprocess.run(cmd_manual, capture_output=True, text=True)
    assert res.returncode == 0
    doc_m = json.loads(res.stdout)
    assert doc_m["schema"] == "sinking-ship-burn-down-v1"
    assert doc_m["delta"] == 1000
    assert doc_m["nfts_per_hour"] == 100.0

    # 2. JSONL metrics input
    jsonl_file = tmp_path / "metrics.jsonl"
    samples = [
        {"status": {"supply_consumed": 500}},
        {"status": {"supply_consumed": 1500}},
    ]
    jsonl_file.write_text(
        "\n".join(json.dumps(s) for s in samples) + "\n", encoding="utf-8"
    )

    cmd_jsonl = [
        sys.executable,
        str(ROOT / "scripts" / "supply_burn_down.py"),
        "--jsonl",
        str(jsonl_file),
    ]
    res_j = subprocess.run(cmd_jsonl, capture_output=True, text=True)
    assert res_j.returncode == 0
    doc_j = json.loads(res_j.stdout)
    assert doc_j["delta"] == 1000


def test_reconcile_budget_report_script(tmp_path: Path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    db_path = tmp_path / "ledger.sqlite"

    ledger = SqliteLedger(db_path, caps)
    ledger.close()

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "reconcile_budget_report.py"),
        "--db",
        str(db_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    doc = json.loads(res.stdout)
    assert doc["schema"] == "sinking-ship-budget-report-v1"
    assert doc["ok"] is True
    assert doc["supply_consumed"] == 0
