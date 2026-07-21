# SPDX-License-Identifier: MIT
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_diff_commitments_equal_and_unequal(tmp_path):
    a = {"commitment_hash": "a" * 64, "commitment": {"x": 1}}
    b = {"commitment_hash": "a" * 64, "commitment": {"x": 1}}
    c = {"commitment_hash": "b" * 64, "commitment": {"x": 2}}
    pa = tmp_path / "a.json"
    pb = tmp_path / "b.json"
    pc = tmp_path / "c.json"
    pa.write_text(json.dumps(a), encoding="utf-8")
    pb.write_text(json.dumps(b), encoding="utf-8")
    pc.write_text(json.dumps(c), encoding="utf-8")
    script = ROOT / "scripts" / "diff_commitments.py"
    r = subprocess.run([sys.executable, str(script), str(pa), str(pb)],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0
    r2 = subprocess.run([sys.executable, str(script), str(pa), str(pc)],
                        capture_output=True, text=True, check=False)
    assert r2.returncode == 1
