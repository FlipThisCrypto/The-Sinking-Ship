# SPDX-License-Identifier: MIT
from pathlib import Path
import json, subprocess, sys
def test_round3_surface_flags():
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, str(root/"scripts"/"round3_surface.py")], capture_output=True, text=True, check=True)
    doc = json.loads(r.stdout)
    assert doc["circuit_breaker"] is True
    assert doc["dr_drill"] is True
    assert doc["slo_doc"] is True
