# SPDX-License-Identifier: MIT
"""Tests for render engine CLI script (engine/render_engine.py)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_render_engine_validate_sprites_cli():
    cmd = [
        sys.executable,
        str(ROOT / "engine" / "render_engine.py"),
        "--validate-sprites",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    assert res.returncode == 0


def test_render_engine_sample_render_cli(tmp_path: Path):
    outdir = tmp_path / "renders"
    cmd = [
        sys.executable,
        str(ROOT / "engine" / "render_engine.py"),
        "--sample",
        "1",
        "--sizes",
        "256",
        "--outdir",
        str(outdir),
        "--seed",
        "cli_test",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    assert res.returncode == 0
    assert outdir.is_dir()
    rendered_files = list(outdir.glob("sample_*_256.png"))
    assert len(rendered_files) == 1
