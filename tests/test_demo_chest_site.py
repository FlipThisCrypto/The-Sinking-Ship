# SPDX-License-Identifier: MIT
"""site/demo_chest.json must stay a real chest-manifest-v1 for the reveal demo."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "site" / "demo_chest.json"


def test_demo_chest_is_valid_manifest_shape():
    doc = json.loads(DEMO.read_text(encoding="utf-8"))
    assert doc.get("schema") == "chest-manifest-v1"
    assert isinstance(doc.get("nfts"), list) and len(doc["nfts"]) >= 1
    assert doc.get("quantity") == len(doc["nfts"])
    assert isinstance(doc.get("manifest_hash"), str) and len(doc["manifest_hash"]) == 64
    assert doc.get("zone")
    assert doc.get("tier")
    for e in doc["nfts"]:
        assert e.get("type") in ("generated", "grail")
        if e["type"] == "generated":
            assert e.get("rarity_tier")
            assert isinstance(e.get("traits"), dict)
