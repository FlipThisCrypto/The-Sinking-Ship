# SPDX-License-Identifier: MIT
"""Tests for social card and brand asset generation scripts."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def test_gen_og_image_script(tmp_path: Path):
    out_png = tmp_path / "og_test.png"
    out_jpg = tmp_path / "og_test.jpg"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "gen_og_image.py"),
        "--out",
        str(out_png),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_png.is_file()
    assert out_jpg.is_file()

    with Image.open(out_png) as img:
        assert img.size == (1200, 630)


def test_gen_share_card_script(tmp_path: Path):
    # 1. Direct arguments
    out_direct = tmp_path / "share_direct.png"
    cmd_direct = [
        sys.executable,
        str(ROOT / "scripts" / "gen_share_card.py"),
        "--rarity",
        "legendary",
        "--zone",
        "hadal",
        "--qty",
        "50",
        "--out",
        str(out_direct),
    ]
    res_d = subprocess.run(cmd_direct, capture_output=True, text=True)
    assert res_d.returncode == 0
    assert out_direct.is_file()

    with Image.open(out_direct) as img:
        assert img.size == (1200, 630)

    # 2. From demo chest manifest
    out_manifest = tmp_path / "share_manifest.png"
    demo_manifest = ROOT / "site" / "demo_chest.json"
    cmd_manifest = [
        sys.executable,
        str(ROOT / "scripts" / "gen_share_card.py"),
        "--from-manifest",
        str(demo_manifest),
        "--out",
        str(out_manifest),
    ]
    res_m = subprocess.run(cmd_manifest, capture_output=True, text=True)
    assert res_m.returncode == 0
    assert out_manifest.is_file()


def test_build_brand_assets_script(tmp_path: Path):
    src_dir = tmp_path / "src_art"
    brand_dir = tmp_path / "brand_out"
    og_out = tmp_path / "og_out.png"
    src_dir.mkdir()

    # Create dummy source icon and banner
    Image.new("RGB", (800, 800), (200, 50, 50)).save(src_dir / "icon.png")
    Image.new("RGB", (2000, 500), (50, 50, 200)).save(src_dir / "banner.png")

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "build_brand_assets.py"),
        "--src-dir",
        str(src_dir),
        "--brand-dir",
        str(brand_dir),
        "--og-out",
        str(og_out),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert (brand_dir / "icon.jpg").is_file()
    assert (brand_dir / "banner.jpg").is_file()
    assert og_out.is_file()

    with Image.open(brand_dir / "icon.jpg") as icon:
        assert icon.size == (600, 600)
    with Image.open(brand_dir / "banner.jpg") as banner:
        assert banner.size == (1600, 400)

