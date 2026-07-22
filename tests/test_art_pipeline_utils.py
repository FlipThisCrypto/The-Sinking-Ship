# SPDX-License-Identifier: MIT
"""Tests for contact sheet composition and manifest validation CLI scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def test_make_contact_sheet_script(tmp_path: Path):
    out_sheet = tmp_path / "contact.png"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "make_contact_sheet.py"),
        "--count",
        "4",
        "--cell",
        "128",
        "--out",
        str(out_sheet),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_sheet.is_file()

    with Image.open(out_sheet) as img:
        assert img.width > 0
        assert img.height > 0


def test_validate_manifest_file_script(tmp_path: Path):
    # 1. Valid manifest
    valid_manifest = tmp_path / "valid_chest.json"
    valid_doc = {
        "schema": "chest-manifest-v1",
        "tier": "castaway",
        "quantity": 1,
        "nfts": [
            {
                "type": "generated",
                "slot": 1,
                "global_index": 1,
                "rarity_tier": "common",
            }
        ],
        "manifest_hash": "a" * 64,
    }
    valid_manifest.write_text(json.dumps(valid_doc), encoding="utf-8")

    cmd_valid = [
        sys.executable,
        str(ROOT / "scripts" / "validate_manifest_file.py"),
        str(valid_manifest),
    ]
    res_v = subprocess.run(cmd_valid, capture_output=True, text=True)
    assert res_v.returncode == 0
    doc_v = json.loads(res_v.stdout)
    assert doc_v["ok"] is True

    # 2. Invalid manifest (schema mismatch)
    invalid_manifest = tmp_path / "invalid_chest.json"
    invalid_doc = {
        "schema": "wrong-schema-v0",
        "quantity": 1,
        "nfts": [],
        "manifest_hash": "short",
    }
    invalid_manifest.write_text(json.dumps(invalid_doc), encoding="utf-8")

    cmd_invalid = [
        sys.executable,
        str(ROOT / "scripts" / "validate_manifest_file.py"),
        str(invalid_manifest),
    ]
    res_inv = subprocess.run(cmd_invalid, capture_output=True, text=True)
    assert res_inv.returncode == 1
    doc_inv = json.loads(res_inv.stdout)
    assert doc_inv["ok"] is False
