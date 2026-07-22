# SPDX-License-Identifier: MIT
"""Tests for placeholder sprite generator script."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_mood_mapping_and_det():
    spec = importlib.util.spec_from_file_location(
        "gps", ROOT / "scripts" / "gen_placeholder_sprites.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test mood mapping
    assert mod.mood_for("Blood Moon Meteor") == "crimson"
    assert mod.mood_for("Golden Treasure Sunset") == "gold"
    assert mod.mood_for("Aurora Emerald") == "green"
    assert mod.mood_for("Unknown Trait Name") == "blue"

    # Test deterministic parameter generator
    det = mod.Det("test_sprite_key_001")
    assert 0 <= det.byte(0) <= 255
    assert 0.0 <= det.frac(1, 0.0, 1.0) <= 1.0
    pick = det.pick(["a", "b", "c"], 2)
    assert pick in ["a", "b", "c"]


def test_gen_placeholder_sprites_cli_help():
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "gen_placeholder_sprites.py"),
        "--help",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Generate PLACEHOLDER sprites" in res.stdout
