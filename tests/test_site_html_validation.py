# SPDX-License-Identifier: MIT
"""Tests for site HTML validation script."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_site_html_validation_script():
    cmd = [sys.executable, str(ROOT / "scripts" / "validate_site_html.py")]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "ok" in res.stdout
