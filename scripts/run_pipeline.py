# SPDX-License-Identifier: MIT
"""End-to-end pipeline smoke run (session close-out requirement).

    validate configs
    -> simulate 44,444 mints (flat profile)
    -> validate sprite tree, render 25 samples from placeholders
    -> commit (test salt) -> roll 5 chests across tiers -> verify each
    -> generate CHIP-0007 metadata for all 5 chests
    -> print a results summary

Everything runs with an explicit TEST salt and is safe to re-run; outputs
land in output/pipeline/ (gitignored).

Usage:
    python scripts/run_pipeline.py [--samples 25] [--skip-render]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "pipeline"
PY = sys.executable

TEST_SALT = b"pipeline-test-salt-NOT-FOR-MAINNET-0001"
TEST_CHESTS = [  # (tier, pass_ordinal, start_index) — spread across the table
    ("castaway", 41, 101),
    ("scuba_diver", 7, 5001),
    ("submarine_captain", 88, 12001),
    ("harbormaster", 3, 30001),
    ("admiral", 2, 40001),
]


def run(step: str, argv: list[str]) -> float:
    print(f"\n=== {step} ===", flush=True)
    t0 = time.perf_counter()
    r = subprocess.run([PY, *argv], cwd=ROOT)
    dt = time.perf_counter() - t0
    if r.returncode != 0:
        print(f"PIPELINE FAILED at: {step} (exit {r.returncode})")
        sys.exit(r.returncode)
    print(f"--- {step}: OK in {dt:.1f}s")
    return dt


def coin_for(tier: str, ordinal: int) -> str:
    import hashlib
    return hashlib.sha256(f"pipeline-coin:{tier}:{ordinal}".encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--samples", type=int, default=25)
    ap.add_argument("--skip-render", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    salt_file = OUT / "test.salt"
    salt_file.write_bytes(TEST_SALT)

    run("1. validate configs", ["engine/validate_configs.py"])
    run("2. simulate 44,444 mints (flat)",
        ["engine/simulate.py", "--profile", "flat", "--mints", "44444",
         "--seed", "pipeline", "--json", str(OUT / "simulate_flat.json")])
    run("2b. simulate full sellout (supply model)",
        ["engine/simulate.py", "--profile", "sellout", "--seed", "pipeline",
         "--json", str(OUT / "simulate_sellout.json")])

    if not args.skip_render:
        run("3. validate sprites", ["engine/render_engine.py", "--validate-sprites"])
        run(f"3b. render {args.samples} samples (active render profile)",
            ["engine/render_engine.py", "--sample", str(args.samples),
             "--seed", "pipeline-samples", "--outdir", str(OUT / "renders")])

    run("4. provenance commitment",
        ["engine/chest_roller.py", "commit", "--salt-file", str(salt_file),
         "--outdir", str(OUT / "commitment")])

    for tier, ordinal, start in TEST_CHESTS:
        run(f"5. roll chest: {tier}",
            ["engine/chest_roller.py", "roll", "--tier", tier,
             "--coin-id", coin_for(tier, ordinal), "--salt-file", str(salt_file),
             "--pass-ordinal", str(ordinal), "--start-index", str(start),
             "--outdir", str(OUT / "chests")])

    for p in sorted((OUT / "chests").glob("chest_*.json")):
        run(f"6. verify {p.name}",
            ["engine/chest_roller.py", "verify", "--manifest", str(p),
             "--salt-file", str(salt_file)])

    run("7. CHIP-0007 metadata (batch)",
        ["engine/metadata_gen.py", "--batch", str(OUT / "chests"),
         "--outdir", str(OUT / "metadata")])

    run("8. rebuild site data", ["scripts/build_site_data.py"])

    # ---- summary ----
    print("\n" + "=" * 64)
    print("PIPELINE SUMMARY")
    print("=" * 64)
    flat = json.loads((OUT / "simulate_flat.json").read_text())
    sell = json.loads((OUT / "simulate_sellout.json").read_text())
    print(f"sellout sim within ±5% (ACCEPTANCE): {sell['within_tolerance']}")
    print(f"flat luck-free sim within ±5%:       {flat['within_tolerance']} "
          f"(informational — targets apply to the sellout mixture, ADR-0006/OQ-5; "
          f"a luck-free pool runs rarer than the minted collection by design)")
    print(f"sellout supply consumed:       {sell['total_supply_consumed']} "
          f"(budget 44,000 — OQ-1 resolved via Snorkeler pass trim)")
    chests = sorted((OUT / "chests").glob("chest_*.json"))
    total_nfts = 0
    for p in chests:
        m = json.loads(p.read_text())
        total_nfts += m["generated_count"]
        grails = m["quantity"] - m["generated_count"]
        print(f"chest {m['tier']:<18} qty={m['quantity']:>3} "
              f"(gen {m['generated_count']}, grails {grails}, "
              f"torn {len(m['the_torn_indices'])}, pity {len(m['pity_upgraded_slots'])}) "
              f"hash {m['manifest_hash'][:12]}…")
    meta_files = list((OUT / "metadata").glob("*.json"))
    renders = list((OUT / "renders").glob("sample_*_2048.png")) if not args.skip_render else []
    print(f"metadata files emitted:        {len(meta_files)} (= {total_nfts} generated NFTs)")
    if not args.skip_render:
        print(f"sample renders (active profile): {len(renders)} NFTs")
    print("all chests verified:           True")
    print("outputs in output/pipeline/ (gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
