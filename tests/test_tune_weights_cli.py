# SPDX-License-Identifier: MIT
"""Tests for rarity weight tuning script (ADR-0006)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_tune_weights_script(tmp_path: Path):
    out_weights = tmp_path / "weights_test.json"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "tune_weights.py"),
        "--polish-iters",
        "1",
        "--replicates",
        "1",
        "--out",
        str(out_weights),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_weights.is_file()

    doc = json.loads(out_weights.read_text(encoding="utf-8"))
    assert doc["config_name"] == "weights"
    assert "weights" in doc
    assert "bucket_scales" in doc
