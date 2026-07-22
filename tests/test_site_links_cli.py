# SPDX-License-Identifier: MIT
"""Tests for site asset and link checker script."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_local_target_resolution():
    spec = importlib.util.spec_from_file_location(
        "csl", ROOT / "scripts" / "check_site_links.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    base = ROOT / "site" / "index.html"
    # External URLs -> None
    assert mod.local_target(base, "https://example.com/art.png") is None
    # Fragment / mailto -> None
    assert mod.local_target(base, "#section") is None
    assert mod.local_target(base, "mailto:test@example.com") is None
    # Local relative link
    target = mod.local_target(base, "assets/brand/icon.jpg")
    assert target is not None
    assert target.name == "icon.jpg"


def test_check_site_links_script():
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "check_site_links.py"),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "check_site_links: ok" in res.stdout
