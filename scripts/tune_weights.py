# SPDX-License-Identifier: MIT
"""Produce config/weights.json tuned to the spec 4.1 rarity targets (P3).

Method (ADR-0006):
 1. Initialize every trait at its spec 4.2 bucket base weight (milli-units).
 2. Hold the None share of each optional layer at a fixed design value.
 3. Analytically calibrate one global scale factor per bucket so that the
    depth-luck-weighted full-sellout mixture of tier probabilities hits the
    targets under an independence model (fast, no MC noise).
 4. Polish the scale factors through the REAL roll engine (constraints,
    rejection, pity, quotas, grails included) with replicated full-sellout
    Monte Carlo runs, until every tier is within --polish-tol relative error.
 5. Write config/weights.json with integer milli-weights and full method
    metadata. Deterministic: fixed seeds, byte-stable output.

Usage:
    python scripts/tune_weights.py [--polish-iters 10] [--replicates 3]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from shipgen import RARITY_ORDER, RARITY_RANK  # noqa: E402
from shipgen.config import GenConfig, CONFIG_DIR  # noqa: E402

log = logging.getLogger("tune_weights")

BASE_WEIGHTS = {  # spec Section 4.2, milli-units
    "common": 100_000, "uncommon": 40_000, "rare": 15_000,
    "epic": 5_000, "legendary": 1_500, "mythic": 400,
}
NONE_SHARES_PERMILLE = {  # design knobs, documented in weights.json meta
    "scene_element": 600,   # "None (majority of supply)" — spec 3.3
    "mouth": 400,
    "hat": 250,
    "aura": 925,            # ~7.5% base aura rate -> ~8% after mythic forcing (spec 3.11)
}
TARGET_COUNTS = {  # spec 4.1 over the generated pool of 44,400 (grails excluded)
    "common": 19000, "uncommon": 12000, "rare": 8000,
    "epic": 3500, "legendary": 1500, "mythic": 400,
}
GENERATED_POOL = 44400
EPIC_RANK = RARITY_RANK["epic"]


def build_weights(cfg: GenConfig, scales: dict[str, float]) -> dict:
    """weights[layer][trait] as integer milli-weights."""
    out: dict[str, dict[str, int]] = {}
    for layer in cfg.layers:
        lw: dict[str, int] = {}
        non_none_total = 0
        for t in layer.traits:
            if t.rarity_bucket in ("none", "quota"):
                continue
            w = max(1, round(BASE_WEIGHTS[t.rarity_bucket] * scales[t.rarity_bucket]))
            lw[t.name] = w
            non_none_total += w
        for t in layer.traits:
            if t.rarity_bucket == "quota":
                lw[t.name] = 0  # never weight-rolled; assigned via committed slots
            elif t.rarity_bucket == "none":
                share = NONE_SHARES_PERMILLE[layer.name]
                lw[t.name] = max(1, round(share / (1000 - share) * non_none_total))
        out[layer.name] = {t.name: lw[t.name] for t in layer.traits}
    return out


def tier_mixture(cfg: GenConfig) -> list[tuple[int, float]]:
    """(luck_permille, generated-share) per tier at expected full sellout."""
    rows = []
    total = 0
    for t in cfg.tiers_doc["tiers"]:
        gen = t["expected_supply"]
        if t["guarantee"]:
            if t["guarantee"].get("guaranteed_grail"):
                gen -= 1
            if t["guarantee"].get("grail_lottery"):
                gen -= cfg.grail_seeding["admiral_chests"]
        rows.append([t["depth_luck_permille"], gen])
        total += gen
    return [(luck, gen / total) for luck, gen in rows]


def analytic_distribution(cfg: GenConfig, weights: dict,
                          mixture: list[tuple[int, float]]) -> dict[str, float]:
    """Independence-model tier distribution under the sellout luck mixture."""
    layer_masses = []
    for layer in cfg.layers:
        none_mass = 0
        per_rank = [0] * 6
        for t in layer.traits:
            w = weights[layer.name][t.name]
            if t.rarity_rank < 0:
                none_mass += w
            else:
                per_rank[t.rarity_rank] += w
        layer_masses.append((none_mass, per_rank))

    dist = {name: 0.0 for name in RARITY_ORDER}
    for luck, share in mixture:
        cums = []
        for b in range(6):
            prod = 1.0
            for none_mass, per_rank in layer_masses:
                scaled = [m * (luck / 1000 if r >= EPIC_RANK else 1.0)
                          for r, m in enumerate(per_rank)]
                total = none_mass + sum(scaled)
                le_b = none_mass + sum(scaled[: b + 1])
                prod *= le_b / total
            cums.append(prod)
        for b in range(6):
            p = cums[b] - (cums[b - 1] if b else 0.0)
            dist[RARITY_ORDER[b]] += share * p
    return dist


def measured_distribution(seeds: list[str]) -> dict[str, float]:
    """Full-sellout MC through the real engine, averaged over seeds."""
    from shipgen.roll import RollEngine
    import simulate as simmod

    cfg = GenConfig()
    engine = RollEngine(cfg)
    tiers: Counter = Counter()
    for seed in seeds:
        stats = simmod.run_sellout(engine, seed)
        tiers.update(stats["tiers"])
    total = sum(tiers.values())
    return {name: tiers.get(name, 0) / total for name in RARITY_ORDER}


def write_weights(cfg: GenConfig, weights: dict, scales: dict[str, float],
                  targets: dict[str, float], polish_report: list[dict]) -> Path:
    doc = {
        "$schema": "./schemas/weights.schema.json",
        "config_name": "weights",
        "version": "1.0.0",
        "method": {
            "generator": "scripts/tune_weights.py",
            "adr": "ADR-0006",
            "base_weights_milli": BASE_WEIGHTS,
            "description": (
                "per-trait weight = spec 4.2 bucket base weight x global bucket scale, "
                "in integer milli-units; None weights hold the design None-shares; "
                "scales calibrated analytically then polished through the real roll "
                "engine on full-sellout Monte Carlo (see polish_report)"),
            "tuning_objective": (
                "depth-luck-weighted FULL-SELLOUT mixture matches spec 4.1 proportions "
                "(interpretation decision OQ-5: 4.1 describes the final collection, "
                "which is minted through luck-bearing tiers, not a luck-free pool)"),
            "polish_report": polish_report,
        },
        "targets": {k: round(v, 9) for k, v in targets.items()},
        "none_shares_permille": NONE_SHARES_PERMILLE,
        # bucket_scales is the AUTHORITATIVE full-precision reproduction value;
        # bucket_scales_permille is a rounded, human-readable diagnostic ONLY
        # (do not recompute weights from it — it loses ~3-4% precision).
        "bucket_scales": {b: repr(s) for b, s in scales.items()},
        "bucket_scales_permille": {b: round(s * 1000) for b, s in scales.items()},
        "weights": weights,
        "depth_luck": {t["name"]: t["depth_luck_permille"] for t in cfg.tiers_doc["tiers"]},
        "guarantees": {t["name"]: t["guarantee"] for t in cfg.tiers_doc["tiers"]},
    }
    path = CONFIG_DIR / "weights.json"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analytic-iters", type=int, default=400)
    ap.add_argument("--polish-iters", type=int, default=10)
    ap.add_argument("--polish-tol", type=float, default=0.025,
                    help="relative tolerance per tier for the polish loop "
                         "(tighter than the ±5%% acceptance bar to leave noise slack)")
    ap.add_argument("--replicates", type=int, default=3,
                    help="full-sellout MC replicates averaged per polish iteration")
    ap.add_argument("--damp", type=float, default=0.6)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = GenConfig(require_weights=False)
    targets = {k: v / GENERATED_POOL for k, v in TARGET_COUNTS.items()}
    mixture = tier_mixture(cfg)
    log.info("sellout luck mixture: %s",
             ", ".join(f"{l / 1000:.2f}x:{s:.3f}" for l, s in mixture))

    # ---- stage 1: analytic calibration ----
    scales = {b: 1.0 for b in BASE_WEIGHTS}
    for i in range(args.analytic_iters):
        weights = build_weights(cfg, scales)
        model = analytic_distribution(cfg, weights, mixture)
        worst = max(abs(model[b] - targets[b]) / targets[b] for b in BASE_WEIGHTS)
        if worst < 0.002:
            log.info("analytic converged after %d iterations (worst rel err %.4f)", i, worst)
            break
        for b in ("mythic", "legendary", "epic", "rare", "uncommon"):
            scales[b] *= (targets[b] / model[b]) ** args.damp
    weights = build_weights(cfg, scales)
    model = analytic_distribution(cfg, weights, mixture)
    log.info("analytic result: %s",
             {b: f"{model[b]*100:.3f}%/{targets[b]*100:.3f}%" for b in RARITY_ORDER})

    # ---- stage 2: polish through the real engine ----
    polish_report = []
    write_weights(cfg, weights, scales, targets, polish_report)
    for it in range(args.polish_iters):
        seeds = [f"tune-{it}-{r}" for r in range(args.replicates)]
        measured = measured_distribution(seeds)
        rels = {b: (measured[b] - targets[b]) / targets[b] for b in BASE_WEIGHTS}
        worst = max(abs(r) for r in rels.values())
        polish_report.append({
            "iteration": it, "seeds": seeds,
            "measured": {b: round(measured[b], 6) for b in RARITY_ORDER},
            "worst_rel_err": round(worst, 5),
        })
        log.info("polish %d: worst rel err %.3f%% | %s", it, worst * 100,
                 " ".join(f"{b}:{rels[b]*+100:+.2f}%" for b in RARITY_ORDER))
        if worst <= args.polish_tol:
            log.info("polish converged")
            break
        for b in ("mythic", "legendary", "epic", "rare", "uncommon"):
            scales[b] *= (targets[b] / measured[b]) ** args.damp
        weights = build_weights(cfg, scales)
        write_weights(cfg, weights, scales, targets, polish_report)
    else:
        log.warning("polish did not reach tolerance within --polish-iters")

    path = write_weights(cfg, weights, scales, targets, polish_report)
    log.info("wrote %s", path)
    log.info("verify with: python engine/simulate.py --profile sellout --seed verify --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
