# SPDX-License-Identifier: MIT
"""Tests for governance decision log, checklist, and circuit snapshot scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_append_decision_log_script(tmp_path: Path):
    log_file = tmp_path / "decisions.jsonl"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "append_decision_log.py"),
        "--log",
        str(log_file),
        "--decision",
        "Approved testnet mint window",
        "--actor",
        "lead-ops",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert log_file.is_file()

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    doc = json.loads(lines[0])
    assert doc["actor"] == "lead-ops"
    assert doc["decision"] == "Approved testnet mint window"
    assert "ts" in doc


def test_gen_governance_checklist_script(tmp_path: Path):
    out_md = tmp_path / "checklist.md"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "gen_governance_checklist.py"),
        "--out",
        str(out_md),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_md.is_file()

    text = out_md.read_text(encoding="utf-8")
    assert date.today().isoformat() in text
    assert "# Mint governance checklist" in text


def test_circuit_snapshot_demo_script():
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "circuit_snapshot_demo.py"),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    doc = json.loads(res.stdout)
    assert "state" in doc
    assert "failures" in doc
