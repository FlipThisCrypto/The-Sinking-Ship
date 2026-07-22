# SPDX-License-Identifier: MIT
"""Tests for visual style grammar scoring script."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_style_score_measurement():
    spec = importlib.util.spec_from_file_location(
        "ss", ROOT / "scripts" / "style_score.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test measurement on one golden reference image
    ref_image = ROOT / "ships_amano" / "ship_01_2048.png"
    if ref_image.exists():
        m = mod.measure(ref_image)
        assert "white_ground" in m
        assert "edge_density" in m
        scores = mod.score_metrics(m)
        assert scores["overall"] > 70.0


def test_style_score_self_check_cli():
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "style_score.py"),
        "--self-check",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Self-check PASS" in res.stdout
