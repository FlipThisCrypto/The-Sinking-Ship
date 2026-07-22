# SPDX-License-Identifier: MIT
"""Validate all config/*.json files against their schemas and each other.

Usage:
    python engine/validate_configs.py [--config-dir config] [--no-weights]

Exit codes: 0 valid, 1 invalid.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from pathlib import Path

from shipgen.config import GenConfig, CONFIG_DIR, load_json
from shipgen.identity import check_chain_identity
from shipgen.schema import SchemaError, validate

log = logging.getLogger("validate_configs")

# Marketplace + render configs are not part of the fairness hash bundle but
# must still validate or CHIP-0007 / the compositor will fail at mint time.
EXTRA_CONFIGS = ("collection", "palette", "render")


def _validate_extra(config_dir: Path) -> None:
    for name in EXTRA_CONFIGS:
        doc = load_json(config_dir / f"{name}.json")
        schema = load_json(config_dir / "schemas" / f"{name}.schema.json")
        validate(doc, schema)
        log.info("%s.json: schema ok", name)
        if name == "collection":
            problems = check_chain_identity(doc)
            if problems:
                raise ValueError(
                    "collection.json chain identity invalid:\n  - "
                    + "\n  - ".join(problems))
            log.info("collection.json: chain identity valid (DID, royalty, id)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config-dir", default=str(CONFIG_DIR))
    ap.add_argument("--no-weights", action="store_true",
                    help="skip weights.json (used before the tuner has produced it)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config_dir = Path(args.config_dir)

    try:
        cfg = GenConfig(config_dir, require_weights=not args.no_weights)
        _validate_extra(config_dir)
    except (OSError, ValueError, SchemaError, json.JSONDecodeError, TypeError, KeyError) as e:
        log.error("config validation FAILED:\n%s", e)
        return 1

    log.info("traits.json: %d layers, %d traits",
             len(cfg.layers), sum(len(ly.traits) for ly in cfg.layers))
    log.info("tiers.json: %d tiers, supply cap %d, public mint budget %d",
             len(cfg.tiers), cfg.supply["cap"], cfg.supply["public_mint_budget"])
    if cfg.weights is not None:
        log.info("weights.json: consistent with traits + tiers")
        log.info("config bundle hash: %s", cfg.config_hash)
    log.info("all configs valid (traits/tiers/weights + collection/palette/render)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
