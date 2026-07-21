# SPDX-License-Identifier: MIT
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_chaos_coinset_script():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "chaos_coinset.py")],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert json.loads(r.stdout)["pass"] is True
