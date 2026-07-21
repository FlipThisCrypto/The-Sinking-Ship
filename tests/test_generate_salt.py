# SPDX-License-Identifier: MIT
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_generate_salt_writes_and_refuses_overwrite(tmp_path):
    out = tmp_path / "a.salt"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_salt.py"),
         "--out", str(out), "--bytes", "24"],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    assert len(out.read_bytes()) == 24
    r2 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_salt.py"),
         "--out", str(out)],
        capture_output=True, text=True, check=False,
    )
    assert r2.returncode == 1
