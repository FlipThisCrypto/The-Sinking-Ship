# SPDX-License-Identifier: MIT
"""Tests for character and ship asset plate installer scripts."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def test_white_to_alpha_transformation():
    spec = importlib.util.spec_from_file_location(
        "ipc", ROOT / "scripts" / "install_polished_characters.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Create dummy white image with a dark red center
    src = Image.new("RGB", (2048, 2048), (255, 255, 255))
    for x in range(800, 1200):
        for y in range(800, 1200):
            src.putpixel((x, y), (180, 20, 20))

    rgba = mod.white_to_alpha(src, threshold=248)
    assert rgba.size == (2048, 2048)
    assert rgba.mode == "RGBA"
    # White background should have 0 alpha
    assert rgba.getpixel((10, 10))[3] == 0
    # Red center should retain full opacity
    assert rgba.getpixel((1000, 1000))[3] == 255

    bone = mod.to_bone(rgba)
    assert bone.size == (2048, 2048)
    assert bone.mode == "RGBA"


def test_install_polished_characters_cli_help():
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "install_polished_characters.py"),
        "--help",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Install polished Tom Bepe" in res.stdout
