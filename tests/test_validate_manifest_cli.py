# SPDX-License-Identifier: MIT
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_validate_demo_chest_cli():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_manifest_file.py"),
         str(ROOT / "site" / "demo_chest.json")],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["ok"] is True


def test_validate_manifest_cli_rejects_bad(tmp_path):
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps({"schema": "nope", "nfts": []}), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_manifest_file.py"), str(bad)],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 1
