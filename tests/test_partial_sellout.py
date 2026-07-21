# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("pps", ROOT / "scripts" / "project_partial_sellout.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_fraction_bounds():
    a = mod.project(0.0)
    assert a["projected_revenue_xch"] == 0
    b = mod.project(1.0)
    assert b["projected_revenue_xch"] > 0
    c = mod.project(0.5)
    assert c["projected_supply"] < b["projected_supply"]
