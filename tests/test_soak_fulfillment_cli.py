# SPDX-License-Identifier: MIT
"""Tests for fulfillment soak stress test script."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_soak_fulfillment_script(tmp_path: Path):
    workdir = tmp_path / "soak_test"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "soak_fulfillment.py"),
        "--purchases",
        "5",
        "--workdir",
        str(workdir),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert (workdir / "soak_report.json").is_file()

    report = json.loads((workdir / "soak_report.json").read_text(encoding="utf-8"))
    assert report["purchases"] == 5
    assert report["pass"] is True
    assert report["status"]["integrity_ok"] is True
