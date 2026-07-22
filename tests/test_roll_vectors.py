# SPDX-License-Identifier: MIT
"""Guard the in-browser full-chest verifier's golden vectors (P8 / Round 2).

The byte-identical JS↔Python check runs in CI via node site/js/verify_roll.mjs;
this keeps a Python-side guard that the vectors exist, stay well-formed, cover
the whole surface (every tier + Torn + grails + pity + forced aura), and are
consistent with a freshly built engine (provenance + config hash)."""
from __future__ import annotations

import json
from pathlib import Path

from shipgen.config import GenConfig
from shipgen.roll import RollEngine, build_commitment, derive_placements

ROOT = Path(__file__).resolve().parent.parent
VECTORS = json.loads((ROOT / "site" / "roll_vectors.json").read_text(encoding="utf-8"))


def test_js_port_and_harness_present():
    for rel in ("site/js/shipgen_roll.js", "site/js/verify_roll.mjs"):
        assert (ROOT / rel).is_file(), f"missing {rel}"


def test_vectors_cover_every_tier():
    cfg = GenConfig()
    all_tiers = {t["name"] for t in cfg.tiers_doc["tiers"]}
    covered = {c["tier"] for c in VECTORS["chests"]}
    assert all_tiers <= covered, f"tiers missing from roll vectors: {all_tiers - covered}"


def test_vectors_cover_hard_paths():
    """At least one embedded full manifest must exercise each hard mechanic."""
    fulls = [c["manifest"] for c in VECTORS["chests"] if "manifest" in c]
    assert fulls, "no full manifests embedded for structural coverage"
    torn = any(m["the_torn_indices"] for m in fulls)
    pity = any(m["pity_upgraded_slots"] for m in fulls)
    grail = any(any(n["type"] == "grail" for n in m["nfts"]) for m in fulls)
    assert torn, "no Torn coverage in embedded manifests"
    assert pity, "no pity-upgrade coverage in embedded manifests"
    assert grail, "no grail coverage in embedded manifests"


def test_vectors_consistent_with_fresh_engine():
    """Provenance + config hash + a sampled manifest must match a rebuild."""
    salt = bytes.fromhex(VECTORS["salt_hex"])
    cfg = GenConfig()
    engine = RollEngine(cfg)
    placements = derive_placements(salt, cfg)
    prov = build_commitment(salt, cfg)["commitment_hash"]

    assert prov == VECTORS["provenance_hash"]
    assert cfg.config_hash == VECTORS["config_version_hash"]

    c = VECTORS["chests"][0]
    m = engine.roll_chest(salt, c["coin_id"], c["tier"], c["pass_ordinal"],
                          c["start_index"], placements, prov)
    assert m["manifest_hash"] == c["manifest_hash"]
