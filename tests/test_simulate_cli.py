# SPDX-License-Identifier: MIT
"""Tests for Monte Carlo simulation CLI script (engine/simulate.py)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_simulate_flat_profile(tmp_path: Path):
    json_out = tmp_path / "sim_flat.json"
    cmd = [
        sys.executable,
        str(ROOT / "engine" / "simulate.py"),
        "--profile",
        "flat",
        "--mints",
        "100",
        "--seed",
        "test_flat",
        "--json",
        str(json_out),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert json_out.is_file()

    doc = json.loads(json_out.read_text(encoding="utf-8"))
    assert doc["profile"] == "flat"
    assert doc["total"] == 100



def test_simulate_sellout_profile(tmp_path: Path):
    json_out = tmp_path / "sim_sellout.json"
    cmd = [
        sys.executable,
        str(ROOT / "engine" / "simulate.py"),
        "--profile",
        "sellout",
        "--seed",
        "test_sellout",
        "--json",
        str(json_out),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert json_out.is_file()

    doc = json.loads(json_out.read_text(encoding="utf-8"))
    assert doc["profile"] == "sellout"
    assert "within_tolerance" in doc
    assert "total_supply_consumed" in doc
