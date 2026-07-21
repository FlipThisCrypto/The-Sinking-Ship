# SPDX-License-Identifier: MIT
"""Compare two metrics JSONL files for health level regressions (CI-friendly)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
def last_level(path):
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        return None
    return json.loads(lines[-1]).get("health", {}).get("level")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before")
    ap.add_argument("--after")
    args = ap.parse_args()
    b, a = last_level(args.before), last_level(args.after)
    rank = {"ok": 0, "degraded": 1, "critical": 2}
    worse = rank.get(a, 9) > rank.get(b, 0)
    print(json.dumps({"before": b, "after": a, "regressed": worse}))
    return 1 if worse else 0
if __name__ == "__main__":
    raise SystemExit(main())
