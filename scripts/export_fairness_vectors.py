# SPDX-License-Identifier: MIT
"""Export cross-language golden vectors for the JS shipgen port (P8/P9).

Writes site/fairness_vectors.json — DRBG KAT + one commitment/manifest hash
from the Python engine. Browser verifiers must match these exactly.

Usage:
    python scripts/export_fairness_vectors.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from shipgen.config import GenConfig  # noqa: E402
from shipgen.drbg import ALGORITHM_ID, Drbg, derive_seed_key  # noqa: E402
from shipgen.roll import RollEngine, build_commitment, derive_placements  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEST_SALT = b"test-salt-for-the-sinking-ship-0001"
COIN_A = "aa" * 32


def main() -> int:
    cfg = GenConfig()
    engine = RollEngine(cfg)
    commitment = build_commitment(TEST_SALT, cfg)
    placements = derive_placements(TEST_SALT, cfg)
    manifest = engine.roll_chest(
        TEST_SALT, COIN_A, "castaway", 7, 42, placements, "prov-test",
    )

    d = Drbg(b"sinking-ship-test-vector", "kat/v1")
    kat = [d.rand_below(1_000_000) for _ in range(5)]

    seed = derive_seed_key(TEST_SALT, "0x" + COIN_A.upper())
    doc = {
        "schema": "sinking-ship-fairness-vectors-v1",
        "rng_algorithm": ALGORITHM_ID,
        "engine": "shipgen-1.0.0",
        "config_hash": cfg.config_hash,
        "drbg_kat": {
            "seed_key_utf8": "sinking-ship-test-vector",
            "label": "kat/v1",
            "rand_below_1e6": kat,
        },
        "coin_normalization": {
            "input": "0x" + COIN_A.upper(),
            "normalized": COIN_A,
            "seed_key_hex": seed.hex(),
        },
        "commitment": {
            "salt_hex": TEST_SALT.hex(),
            "commitment_hash": commitment["commitment_hash"],
        },
        "sample_manifest": {
            "tier": "castaway",
            "pass_ordinal": 7,
            "start_index": 42,
            "coin_id": COIN_A,
            "provenance_commitment_override": "prov-test",
            "manifest_hash": manifest["manifest_hash"],
            "quantity": manifest["quantity"],
            "rarity_tiers": [
                e.get("rarity_tier", "grail") for e in manifest["nfts"]
            ],
        },
        "verify_cli": (
            "python engine/chest_roller.py verify "
            "--manifest <chest.json> --salt-file <revealed.salt>"
        ),
    }
    out = ROOT / "site" / "fairness_vectors.json"
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
