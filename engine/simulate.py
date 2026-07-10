# SPDX-License-Identifier: MIT
"""Monte Carlo simulator for THE SINKING SHIP generation (P3).

Two profiles:

  flat     — N independent mints at a fixed Depth Luck (default 1.0x).
  sellout  — the full Section 5.2 tier table: every pass of every tier rolls
             a real chest through the real roll engine (quantities, Depth
             Luck, pity guarantees, grail seeding, The Torn quota), then the
             achieved rarity distribution and total supply consumption are
             reported against the Section 4.1 targets and the supply budget.

The rarity targets (spec 4.1, generated pool = 44,400 after the 44 grails)
are read from weights.json `targets`. With --check the exit code is 2 when
any tier misses the ±5% relative tolerance — CI-able.

Usage:
    python engine/simulate.py --profile sellout --seed sim1 --check
    python engine/simulate.py --profile flat --mints 44444 --seed sim1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections import Counter

from shipgen import RARITY_ORDER
from shipgen.config import GenConfig
from shipgen.roll import RollEngine, derive_placements

log = logging.getLogger("simulate")

TOLERANCE = 0.05


def sim_salt(seed: str) -> bytes:
    return hashlib.sha256(f"sinking-ship-sim:{seed}".encode()).digest()


def synthetic_coin(seed: str, tier: str, pass_ordinal: int) -> str:
    return hashlib.sha256(f"simcoin:{seed}:{tier}:{pass_ordinal}".encode()).hexdigest()


def run_flat(engine: RollEngine, mints: int, seed: str, luck: int) -> Counter:
    salt = sim_salt(seed)
    tiers = Counter()
    for i in range(mints):
        nft = engine.roll_nft(salt, f"flat/{i}", luck)
        tiers[nft.rarity_tier] += 1
    return tiers


def run_sellout(engine: RollEngine, seed: str, per_trait: Counter | None = None) -> dict:
    cfg = engine.cfg
    salt = sim_salt(seed)
    placements = derive_placements(salt, cfg)
    tiers = Counter()
    stats = {
        "generated": 0, "grails": 0, "torn": 0, "pity_upgrades": 0,
        "per_tier_supply": {}, "revenue_xch": 0.0,
    }
    start_index = 1
    for tier in cfg.tiers_doc["tiers"]:
        name = tier["name"]
        tier_supply = 0
        for p in range(1, tier["passes"] + 1):
            coin = synthetic_coin(seed, name, p)
            m = engine.roll_chest(salt, coin, name, p, start_index,
                                  placements, "sim-provenance")
            start_index += m["generated_count"]
            tier_supply += m["quantity"]
            stats["generated"] += m["generated_count"]
            stats["grails"] += m["quantity"] - m["generated_count"]
            stats["torn"] += len(m["the_torn_indices"])
            stats["pity_upgrades"] += len(m["pity_upgraded_slots"])
            for e in m["nfts"]:
                if e["type"] == "generated":
                    tiers[e["rarity_tier"]] += 1
                    if per_trait is not None:
                        for layer, trait in e["traits"].items():
                            per_trait[(layer, trait)] += 1
        stats["per_tier_supply"][name] = tier_supply
        if tier["price_xch"]:
            stats["revenue_xch"] += float(tier["price_xch"]) * tier["passes"]
    stats["total_supply_consumed"] = stats["generated"] + stats["grails"]
    stats["tiers"] = tiers
    return stats


def report_distribution(tiers: Counter, targets: dict, total: int) -> bool:
    ok = True
    print(f"\n{'tier':<11} {'target%':>9} {'achieved%':>10} {'rel delta':>10}  status")
    print("-" * 52)
    for name in reversed(RARITY_ORDER):
        target = targets[name]
        achieved = tiers.get(name, 0) / total
        rel = (achieved - target) / target
        good = abs(rel) <= TOLERANCE
        ok &= good
        print(f"{name:<11} {target*100:>8.3f}% {achieved*100:>9.3f}% "
              f"{rel*100:>+9.2f}%  {'OK' if good else 'MISS'}")
    print(f"{'n =':<11} {total}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", choices=["flat", "sellout"], default="sellout")
    ap.add_argument("--mints", type=int, default=44444, help="flat profile: number of mints")
    ap.add_argument("--seed", default="sim1")
    ap.add_argument("--replicates", type=int, default=1,
                    help="average N independent runs (seed-0..seed-N-1). The mythic tier "
                         "has only ~400 expected members, so a SINGLE run carries ~5%% "
                         "Poisson noise at 1 sigma — use >=5 replicates for acceptance checks")
    ap.add_argument("--luck", type=int, default=1000, help="flat profile: depth luck permille")
    ap.add_argument("--check", action="store_true", help="exit 2 unless within ±5%%")
    ap.add_argument("--per-trait", metavar="FILE", help="write per-trait counts JSON (sellout)")
    ap.add_argument("--json", metavar="FILE", help="write full results JSON")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = GenConfig()
    engine = RollEngine(cfg)
    targets = cfg.weights_doc["targets"]

    seeds = ([args.seed] if args.replicates <= 1
             else [f"{args.seed}-{r}" for r in range(args.replicates)])

    if args.profile == "flat":
        log.info("flat simulation: %d mints x %d replicate(s), luck %d permille, seed %r",
                 args.mints, len(seeds), args.luck, args.seed)
        tiers = Counter()
        for s in seeds:
            tiers.update(run_flat(engine, args.mints, s, args.luck))
        total = sum(tiers.values())
        ok = report_distribution(tiers, targets, total)
        results = {"profile": "flat", "seeds": seeds, "luck": args.luck,
                   "tiers": dict(tiers), "total": total, "within_tolerance": ok}
    else:
        log.info("full-sellout simulation x %d replicate(s), seed %r",
                 len(seeds), args.seed)
        per_trait = Counter() if args.per_trait else None
        tiers = Counter()
        stats = None
        for s in seeds:
            rep = run_sellout(engine, s, per_trait)
            tiers.update(rep.pop("tiers"))
            stats = rep  # supply stats reported from the last replicate
        total = sum(tiers.values())
        ok = report_distribution(tiers, targets, total)

        budget = cfg.supply["public_mint_budget"]
        consumed = stats["total_supply_consumed"]
        print(f"\nsupply consumed at full sellout: {consumed}")
        print(f"public mint budget (cap - reserve): {budget}")
        overflow = consumed - budget
        if overflow > 0:
            print(f"OVERFLOW: {overflow} NFTs beyond budget "
                  f"(spec conflict OQ-1 — see tiers.json supply notes)")
        else:
            print(f"headroom: {-overflow}")
        print(f"grails seeded into chests: {stats['grails']}")
        print(f"The Torn assigned: {stats['torn']} / 44 committed slots "
              f"(slots beyond the minted range never occur)")
        print(f"pity upgrades applied: {stats['pity_upgrades']}")
        print(f"full sellout revenue: {stats['revenue_xch']:.2f} XCH")
        results = {"profile": "sellout", "seeds": seeds, "tiers": dict(tiers),
                   "total": total, "within_tolerance": ok, **stats}
        if args.per_trait:
            counts = {f"{layer}/{trait}": n
                      for (layer, trait), n in sorted(per_trait.items())}
            with open(args.per_trait, "w", encoding="utf-8", newline="\n") as f:
                json.dump(counts, f, indent=2)
            log.info("per-trait counts written to %s", args.per_trait)

    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(results, f, indent=2, default=str)
        log.info("results written to %s", args.json)

    if args.check and not ok:
        log.error("distribution outside ±5%% tolerance")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
