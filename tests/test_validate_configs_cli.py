# SPDX-License-Identifier: MIT
"""Tests for config validation CLI script (engine/validate_configs.py)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_validate_configs_script():
    cmd = [
        sys.executable,
        str(ROOT / "engine" / "validate_configs.py"),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    assert res.returncode == 0
    assert "all configs valid" in res.stderr or "all configs valid" in res.stdout
