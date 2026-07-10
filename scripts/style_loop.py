# SPDX-License-Identifier: MIT
"""Regenerate illustration stand-ins, sample composites, and score vs ships_amano.

Usage:
    python scripts/style_loop.py
    python scripts/style_loop.py --samples 12 --seed loop2 --threshold 92
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--seed", default="style")
    ap.add_argument("--threshold", type=float, default=92.0)
    ap.add_argument("--skip-sprites", action="store_true",
                    help="only re-render + score (sprites already current)")
    ap.add_argument("--outdir", default="output/style_loop")
    args = ap.parse_args()

    py = sys.executable
    if not args.skip_sprites:
        rc = run([py, "scripts/gen_placeholder_sprites.py", "--force",
                  "--profile", "illustration"])
        if rc:
            return rc

    out = args.outdir
    rc = run([
        py, "engine/render_engine.py",
        "--sample", str(args.samples),
        "--seed", args.seed,
        "--outdir", out,
        "--sizes", "512",
    ])
    if rc:
        return rc

    return run([
        py, "scripts/style_score.py",
        "--samples", out,
        "--threshold", str(args.threshold),
        "--json-out", str(Path(out) / "score.json"),
    ])


if __name__ == "__main__":
    sys.exit(main())
