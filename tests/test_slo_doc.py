# SPDX-License-Identifier: MIT
from pathlib import Path
def test_slo_doc_exists_and_has_table():
    text = (Path(__file__).resolve().parent.parent / "docs" / "SLO.md").read_text(encoding="utf-8")
    assert "Roll-core p95" in text
    assert "Ledger integrity" in text
