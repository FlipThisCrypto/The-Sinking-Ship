# SPDX-License-Identifier: MIT
"""Load-test chest rolls (CPU path). Target: p95 roll < 100ms per chest.

Simulates N concurrent-style sequential rolls through the real engine
(no chain). Prints latency histogram and exit 1 if p95 exceeds --p95-ms.

Usage:
    python scripts/load_test_rolls.py
    python scripts/load_test_rolls.py --chests 200 --p95-ms 100
"""
from __future__ import annotations

import argparse
import hashlib
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from shipgen.config import GenConfig  # noqa: E402
from shipgen.roll import RollEngine, derive_placements  # noqa: E402

SALT = b"load-test-salt-NOT-FOR-MAINNET-0001"


def pct(sorted_ms: list[float], p: float) -> float:
    if not sorted_ms:
        return 0.0
    k = min(len(sorted_ms) - 1, max(0, int(round((p / 100.0) * (len(sorted_ms) - 1)))))
    return sorted_ms[k]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chests", type=int, default=200)
    ap.add_argument("--tier", default="castaway")
    ap.add_argument("--p95-ms", type=float, default=100.0)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    cfg = GenConfig()
    engine = RollEngine(cfg)
    placements = derive_placements(SALT, cfg)
    tier = cfg.tiers[args.tier]
    times: list[float] = []
    start_index = 1

    t0 = time.perf_counter()
    for i in range(args.chests):
        coin = hashlib.sha256(f"load:{i}".encode()).hexdigest()
        ordinal = 1 + (i % tier["passes"])
        t1 = time.perf_counter()
        m = engine.roll_chest(
            SALT, coin, args.tier, ordinal, start_index, placements, "load-prov")
        times.append((time.perf_counter() - t1) * 1000.0)
        start_index += m["generated_count"]
    wall = time.perf_counter() - t0

    times_sorted = sorted(times)
    report = {
        "chests": args.chests,
        "tier": args.tier,
        "wall_s": round(wall, 3),
        "mean_ms": round(statistics.fmean(times), 3),
        "p50_ms": round(pct(times_sorted, 50), 3),
        "p95_ms": round(pct(times_sorted, 95), 3),
        "p99_ms": round(pct(times_sorted, 99), 3),
        "max_ms": round(times_sorted[-1], 3),
        "target_p95_ms": args.p95_ms,
        "pass": pct(times_sorted, 95) <= args.p95_ms,
    }
    print(json_dumps(report))
    if args.json_out:
        Path(args.json_out).write_text(json_dumps(report) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, indent=2, sort_keys=True)


if __name__ == "__main__":
    sys.exit(main())
