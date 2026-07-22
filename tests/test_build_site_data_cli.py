# SPDX-License-Identifier: MIT
"""Tests for site data compilation script."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_build_site_data_script(tmp_path: Path):
    out_js = tmp_path / "tiers_test.js"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "build_site_data.py"),
        "--out",
        str(out_js),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_js.is_file()

    content = out_js.read_text(encoding="utf-8")
    assert "const SHIP_DATA = {" in content
    assert '"publicMintBudget": 44000' in content
    assert '"HMAC-SHA256-DRBG-v1"' in content
