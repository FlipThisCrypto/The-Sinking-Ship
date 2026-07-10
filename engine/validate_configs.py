# SPDX-License-Identifier: MIT
"""Validate all config/*.json files against their schemas and each other.

Usage:
    python engine/validate_configs.py [--config-dir config] [--no-weights]

Exit codes: 0 valid, 1 invalid.
"""
from __future__ import annotations

import argparse
import logging
import sys

from shipgen.config import GenConfig, CONFIG_DIR

log = logging.getLogger("validate_configs")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config-dir", default=str(CONFIG_DIR))
    ap.add_argument("--no-weights", action="store_true",
                    help="skip weights.json (used before the tuner has produced it)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        cfg = GenConfig(args.config_dir, require_weights=not args.no_weights)
    except Exception as e:
        log.error("config validation FAILED:\n%s", e)
        return 1

    log.info("traits.json: %d layers, %d traits",
             len(cfg.layers), sum(len(l.traits) for l in cfg.layers))
    log.info("tiers.json: %d tiers, supply cap %d, public mint budget %d",
             len(cfg.tiers), cfg.supply["cap"], cfg.supply["public_mint_budget"])
    if cfg.weights is not None:
        log.info("weights.json: consistent with traits + tiers")
        log.info("config bundle hash: %s", cfg.config_hash)
    log.info("all configs valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
