# SPDX-License-Identifier: MIT
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_dr_drill_script_passes(tmp_path):
    work = tmp_path / "dr"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dr_drill.py"),
         "--workdir", str(work)],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    doc = json.loads(r.stdout)
    assert doc["pass"] is True
    assert doc["restored_coin_state"] == "fulfilled"
