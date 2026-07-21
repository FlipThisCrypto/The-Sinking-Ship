# SPDX-License-Identifier: MIT
"""Property-style determinism: many synthetic coins re-roll byte-identical."""
from __future__ import annotations

import hashlib
import json

from shipgen.canon import canon_json
from shipgen.roll import RollEngine, derive_placements

SALT = b"property-determinism-salt-000001"


def test_many_coins_two_pass_identical(cfg):
    engine = RollEngine(cfg)
    placements = derive_placements(SALT, cfg)
    for i in range(25):
        coin = hashlib.sha256(f"prop-coin:{i}".encode()).hexdigest()
        a = engine.roll_chest(SALT, coin, "castaway", 1, 1 + i * 10, placements, "prov")
        b = engine.roll_chest(SALT, coin, "castaway", 1, 1 + i * 10, placements, "prov")
        assert canon_json(a) == canon_json(b)
        assert a["manifest_hash"] == b["manifest_hash"]
        # Re-parse JSON stability
        assert json.loads(canon_json(a))["manifest_hash"] == a["manifest_hash"]


def test_different_coins_diverge(cfg):
    engine = RollEngine(cfg)
    placements = derive_placements(SALT, cfg)
    hashes = set()
    for i in range(15):
        coin = hashlib.sha256(f"diverge:{i}".encode()).hexdigest()
        m = engine.roll_chest(SALT, coin, "castaway", 1, 1000 + i, placements, "prov")
        hashes.add(m["manifest_hash"])
    assert len(hashes) == 15
