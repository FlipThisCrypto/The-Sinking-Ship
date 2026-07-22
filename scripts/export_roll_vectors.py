# SPDX-License-Identifier: MIT
"""Export full-chest golden vectors for the in-browser roll verifier (P8).

Writes site/roll_vectors.json: the committed config docs, a fixed demo salt,
the derived placements + provenance hash, and a battery of fully-rolled chest
manifests spanning every tier (plus deliberate coverage of The Torn, grails,
pity guarantees, and forced auras). The JS port in site/js/shipgen_roll.js must
reproduce every manifest_hash bit-for-bit; site/js/verify_roll.mjs (run in CI)
asserts it.

This salt is a PUBLIC demo salt — never the mint salt.

Usage:
    python scripts/export_roll_vectors.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from shipgen.config import GenConfig, CONFIG_DIR, load_json  # noqa: E402
from shipgen.roll import RollEngine, build_commitment, derive_placements  # noqa: E402

DEMO_SALT = b"sinking-ship-PUBLIC-demo-salt-roll-vectors-v1"
COINS = [
    "11" * 32, "a1b2c3d4" * 8, "deadbeef" * 8,
    "0000000000000000000000000000000000000000000000000000000000000001",
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
]


def _chest(engine, salt, placements, prov, tier, coin, ordinal, start, full=False):
    """A chest record: roll inputs + expected manifest_hash (+ optionally the
    full manifest). Returns (record, full_manifest) so the caller can choose
    which manifests to embed for structural coverage. The JS port re-rolls from
    the inputs and must reproduce the hash; embedded manifests also let the
    verifier diff every field, not just the hash."""
    m = engine.roll_chest(salt, coin, tier, ordinal, start, placements, prov)
    rec = {
        "tier": tier, "coin_id": coin, "pass_ordinal": ordinal,
        "start_index": start, "qty": m["quantity"],
        "manifest_hash": m["manifest_hash"],
    }
    if full:
        rec["manifest"] = m
    return rec, m


def main() -> int:
    cfg = GenConfig()
    engine = RollEngine(cfg)
    placements = derive_placements(DEMO_SALT, cfg)
    commitment = build_commitment(DEMO_SALT, cfg)
    prov = commitment["commitment_hash"]

    torn_slots = placements["torn_slots"]
    pairs = []  # (record, full_manifest)

    def add(tier, coin, ordinal, start):
        pairs.append(_chest(engine, DEMO_SALT, placements, prov, tier, coin, ordinal, start))

    # One chest per tier (pass_ordinal 1) across a rotating set of coins.
    tier_names = [t["name"] for t in cfg.tiers_doc["tiers"]]
    for i, tier in enumerate(tier_names):
        add(tier, COINS[i % len(COINS)], 1, 1 + i * 500)

    # Deep tiers with a second coin — exercise pity + bigger chests.
    for tier in ("submarine_captain", "shipwright", "harbormaster", "admiral",
                 "wizard_of_the_deep"):
        add(tier, COINS[2], 1, 20000)

    # Guaranteed Torn coverage: a 1-NFT Castaway whose global index == a torn slot.
    if torn_slots:
        add("castaway", COINS[3], 1, torn_slots[0])
        add("castaway", COINS[4], 1, torn_slots[len(torn_slots) // 2])

    # Grail coverage: every Admiral pass (lottery) and every mid grail's (tier,pass).
    grails = placements["grails"]
    for p in range(1, next(t["passes"] for t in cfg.tiers_doc["tiers"]
                           if t["name"] == grails["admiral"]["tier"]) + 1):
        add(grails["admiral"]["tier"], COINS[p % len(COINS)], p, 30000 + p)
    for m in grails["mid"]:
        add(m["tier"], COINS[1], m["pass_ordinal"], 35000)

    # Embed the full manifest for the first chest that exercises each hard
    # mechanic (Torn, pity, grail) — guarantees structural coverage regardless
    # of how the demo salt lands. Prefer smaller chests to keep the file lean.
    def _has(kind, man):
        if kind == "torn":
            return bool(man["the_torn_indices"])
        if kind == "pity":
            return bool(man["pity_upgraded_slots"])
        if kind == "grail":
            return any(n["type"] == "grail" for n in man["nfts"])
        return False

    for kind in ("torn", "pity", "grail"):
        best = min((p for p in pairs if _has(kind, p[1]) and "manifest" not in p[0]),
                   key=lambda p: p[1]["quantity"], default=None)
        if best is not None:
            best[0]["manifest"] = best[1]

    chests = [rec for rec, _man in pairs]

    doc = {
        "schema": "sinking-ship-roll-vectors-v1",
        "note": "PUBLIC demo salt. JS must reproduce every manifest_hash.",
        "salt_hex": DEMO_SALT.hex(),
        "provenance_hash": prov,
        "config_version_hash": cfg.config_hash,
        "config": {
            "traits": load_json(CONFIG_DIR / "traits.json"),
            "weights": load_json(CONFIG_DIR / "weights.json"),
            "tiers": load_json(CONFIG_DIR / "tiers.json"),
        },
        "placements": placements,
        "chests": chests,
    }
    out = ROOT / "site" / "roll_vectors.json"
    out.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=True) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"wrote {out} — {len(chests)} chests, salt {DEMO_SALT.hex()[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
