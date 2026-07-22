# SPDX-License-Identifier: MIT
"""Tests for markdown documentation link checker script."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_check_doc_links_script():
    cmd = [sys.executable, str(ROOT / "scripts" / "check_doc_links.py")]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "ok" in res.stdout
