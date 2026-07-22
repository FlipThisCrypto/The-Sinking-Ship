# SPDX-License-Identifier: MIT
"""Tests for the end-to-end pipeline runner script."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_run_pipeline_script():
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_pipeline.py"),
        "--skip-render",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    assert res.returncode == 0, res.stderr + "\n" + res.stdout
    assert "PIPELINE SUMMARY" in res.stdout
    assert "all chests verified:           True" in res.stdout
