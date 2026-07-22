# SPDX-License-Identifier: MIT
"""Tests for config hash stamping and post-mint lock CLI scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from shipgen.config import GenConfig

ROOT = Path(__file__).resolve().parent.parent


def test_stamp_and_check_config_hash_scripts(tmp_path: Path):
    stamp_txt = tmp_path / "mint_config_hash.txt"
    stamp_json = tmp_path / "mint_config_hash.json"

    # 1. Stamp config hash
    cmd_stamp = [
        sys.executable,
        str(ROOT / "scripts" / "stamp_config_hash.py"),
        "--out",
        str(stamp_txt),
        "--json-out",
        str(stamp_json),
    ]
    res_s = subprocess.run(cmd_stamp, capture_output=True, text=True)
    assert res_s.returncode == 0
    assert stamp_txt.is_file()
    assert stamp_json.is_file()

    stamped_hash = stamp_txt.read_text(encoding="utf-8").strip()
    assert stamped_hash == GenConfig().config_hash

    json_doc = json.loads(stamp_json.read_text(encoding="utf-8"))
    assert json_doc["config_hash"] == stamped_hash

    # 2. Check matching stamp
    cmd_check_ok = [
        sys.executable,
        str(ROOT / "scripts" / "check_config_stamp.py"),
        "--stamp",
        str(stamp_txt),
    ]
    res_c_ok = subprocess.run(cmd_check_ok, capture_output=True, text=True)
    assert res_c_ok.returncode == 0
    doc_c_ok = json.loads(res_c_ok.stdout)
    assert doc_c_ok["ok"] is True

    # 3. Check mismatched stamp
    bad_stamp = tmp_path / "bad_stamp.txt"
    bad_stamp.write_text("00" * 32 + "\n", encoding="utf-8")

    cmd_check_bad = [
        sys.executable,
        str(ROOT / "scripts" / "check_config_stamp.py"),
        "--stamp",
        str(bad_stamp),
    ]
    res_c_bad = subprocess.run(cmd_check_bad, capture_output=True, text=True)
    assert res_c_bad.returncode == 1
    doc_c_bad = json.loads(res_c_bad.stdout)
    assert doc_c_bad["ok"] is False


def test_reconcile_if_stamp_ok_script(tmp_path: Path):
    stamp_txt = tmp_path / "mint_config_hash.txt"
    stamp_txt.write_text(GenConfig().config_hash + "\n", encoding="utf-8")

    bad_stamp = tmp_path / "bad_stamp.txt"
    bad_stamp.write_text("ff" * 32 + "\n", encoding="utf-8")

    db_path = tmp_path / "ledger.sqlite"
    salt_file = tmp_path / "test.salt"
    salt_file.write_bytes(b"reconcile-stamp-test-salt-16b")
    fixture = tmp_path / "fixture.json"
    fixture.write_text("[]", encoding="utf-8")

    # 1. Mismatched stamp should abort with exit code 2
    cmd_bad = [
        sys.executable,
        str(ROOT / "scripts" / "reconcile_if_stamp_ok.py"),
        "--stamp",
        str(bad_stamp),
        "--db",
        str(db_path),
        "--salt-file",
        str(salt_file),
        "--fixture",
        str(fixture),
    ]
    res_bad = subprocess.run(cmd_bad, capture_output=True, text=True)
    assert res_bad.returncode == 2
    assert "config_stamp_mismatch" in res_bad.stdout

    # 2. Matching stamp should proceed to reconcile
    cmd_ok = [
        sys.executable,
        str(ROOT / "scripts" / "reconcile_if_stamp_ok.py"),
        "--stamp",
        str(stamp_txt),
        "--db",
        str(db_path),
        "--salt-file",
        str(salt_file),
        "--fixture",
        str(fixture),
    ]
    res_ok = subprocess.run(cmd_ok, capture_output=True, text=True)
    assert res_ok.returncode == 0
