# SPDX-License-Identifier: MIT
"""Tests for ledger invariant and signed audit export CLI scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fulfillment import SqliteLedger
from fulfillment.types import TierPurchase
from shipgen.config import GenConfig

ROOT = Path(__file__).resolve().parent.parent



def test_verify_ledger_invariants_script(tmp_path: Path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    db_path = tmp_path / "ledger.sqlite"
    ledger = SqliteLedger(db_path, caps)
    try:
        ledger.record_purchase(
            TierPurchase(
                coin_id="11" * 32,
                tier_name="castaway",
                buyer_address="xch1test",
                block_height=100,
                network="testnet11",
            )
        )
    finally:
        ledger.close()

    cmd = [sys.executable, str(ROOT / "scripts" / "verify_ledger_invariants.py"), "--db", str(db_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    doc = json.loads(res.stdout)
    assert doc["ok"] is True
    assert doc["problems"] == []


def test_signed_and_verify_audit_export_scripts(tmp_path: Path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    db_path = tmp_path / "ledger.sqlite"
    audit_json = tmp_path / "audit.json"
    ledger = SqliteLedger(db_path, caps)
    try:
        ledger.record_pending_hint(
            TierPurchase(
                coin_id="22" * 32,
                tier_name="castaway",
                buyer_address="xch1test2",
                block_height=101,
                network="testnet11",
            )
        )
    finally:
        ledger.close()



    # 1. Export signed audit
    export_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "signed_audit_export.py"),
        "--db",
        str(db_path),
        "--out",
        str(audit_json),
    ]
    res_exp = subprocess.run(export_cmd, capture_output=True, text=True)
    assert res_exp.returncode == 0
    assert audit_json.is_file()

    # 2. Verify audit export
    verify_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "verify_audit_export.py"),
        str(audit_json),
    ]
    res_ver = subprocess.run(verify_cmd, capture_output=True, text=True)
    assert res_ver.returncode == 0
    doc_ver = json.loads(res_ver.stdout)
    assert doc_ver["ok"] is True

    # 3. Tamper with audit file and verify failure
    tampered_data = json.loads(audit_json.read_text(encoding="utf-8"))
    tampered_data["rows"].append({"tampered": True})
    tampered_json = tmp_path / "tampered_audit.json"
    tampered_json.write_text(json.dumps(tampered_data), encoding="utf-8")

    res_tampered = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_audit_export.py"), str(tampered_json)],
        capture_output=True,
        text=True,
    )
    assert res_tampered.returncode == 1
    doc_tampered = json.loads(res_tampered.stdout)
    assert doc_tampered["ok"] is False


def test_verify_audit_export_missing_content_sha256(tmp_path: Path):
    bad_json = tmp_path / "no_sha.json"
    bad_json.write_text(json.dumps({"schema": "sinking-ship-audit-export-v1", "rows": []}), encoding="utf-8")

    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_audit_export.py"), str(bad_json)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    doc = json.loads(res.stdout)
    assert doc["ok"] is False
    assert "missing content_sha256" in doc["error"]

