# SPDX-License-Identifier: MIT
from scripts import redact_buyer_fields as r
# load via importlib
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("red", ROOT/"scripts"/"redact_buyer_fields.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
def test_redact():
    d = mod.redact({"buyer_address": "txch1abc", "coin_id": "aa"})
    assert d["buyer_address"] == "***REDACTED***"
    assert d["coin_id"] == "aa"
