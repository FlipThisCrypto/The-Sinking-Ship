# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ops_preflight_passes_with_valid_salt(tmp_path):
    salt = tmp_path / "ok.salt"
    salt.write_bytes(b"preflight-salt-OK-0123456789ab")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ops_preflight.py"),
         "--salt-file", str(salt), "--skip-sprites"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    doc = json.loads(r.stdout)
    assert doc["ok"] is True


def test_ops_preflight_fails_short_salt(tmp_path):
    salt = tmp_path / "bad.salt"
    salt.write_bytes(b"short")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ops_preflight.py"),
         "--salt-file", str(salt), "--skip-sprites"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    doc = json.loads(r.stdout)
    assert doc["ok"] is False
