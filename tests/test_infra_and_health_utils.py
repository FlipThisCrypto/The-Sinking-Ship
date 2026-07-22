# SPDX-License-Identifier: MIT
"""Tests for cost modeling, health comparison, and manifest dir hashing scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_compare_health_jsonl_script(tmp_path: Path):
    file_a = tmp_path / "a.jsonl"
    file_b = tmp_path / "b.jsonl"

    file_a.write_text(json.dumps({"health": {"level": "ok"}}) + "\n", encoding="utf-8")
    file_b.write_text(json.dumps({"health": {"level": "degraded"}}) + "\n", encoding="utf-8")

    # 1. Regression ok -> degraded returns exit code 1
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "compare_health_jsonl.py"),
        "--before",
        str(file_a),
        "--after",
        str(file_b),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 1
    doc = json.loads(res.stdout)
    assert doc["before"] == "ok"
    assert doc["after"] == "degraded"
    assert doc["regressed"] is True

    # 2. No regression ok -> ok returns exit code 0
    cmd_same = [
        sys.executable,
        str(ROOT / "scripts" / "compare_health_jsonl.py"),
        "--before",
        str(file_a),
        "--after",
        str(file_a),
    ]
    res_same = subprocess.run(cmd_same, capture_output=True, text=True)
    assert res_same.returncode == 0
    doc_same = json.loads(res_same.stdout)
    assert doc_same["regressed"] is False


def test_cost_model_script():
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "cost_model.py"),
        "--days",
        "7",
        "--rpc-usd-per-day",
        "10.0",
        "--host-usd-per-day",
        "5.0",
        "--xch-usd",
        "25.0",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    doc = json.loads(res.stdout)
    assert doc["schema"] == "sinking-ship-cost-model-v1"
    assert doc["infra_usd"] == 105.0  # (10 + 5) * 7
    assert doc["projected_revenue_xch"] > 0


def test_hash_manifest_dir_script(tmp_path: Path):
    manifest_dir = tmp_path / "chests"
    manifest_dir.mkdir()
    out_json = tmp_path / "dir_hash.json"

    (manifest_dir / "chest_1.json").write_text('{"id": 1}', encoding="utf-8")
    (manifest_dir / "chest_2.json").write_text('{"id": 2}', encoding="utf-8")

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "hash_manifest_dir.py"),
        "--dir",
        str(manifest_dir),
        "--out",
        str(out_json),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_json.is_file()

    doc = json.loads(out_json.read_text(encoding="utf-8"))
    assert doc["schema"] == "sinking-ship-manifest-dir-hash-v1"
    assert len(doc["files"]) == 2
    assert len(doc["root_sha256"]) == 64
