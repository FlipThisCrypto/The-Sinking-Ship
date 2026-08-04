# SPDX-License-Identifier: MIT
"""Apply corrective transforms to externally authored sprite layers.

``body/`` and ``ship_class/`` cannot be regenerated — they were authored outside
this repository — so defects in them are repaired in place. The pre-repair files
remain byte-exact in ``vault/sprites-v1/`` and every transform is checked to
leave the plate's appearance over bone white unchanged.

Usage:
    python scripts/repair_art.py --layer ship_class --check
    python scripts/repair_art.py --layer ship_class --unmatte
    python scripts/repair_art.py --layer ship_class --unmatte --only lifeboat,raft
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from artgen.repair import (  # noqa: E402
    appearance_delta_over_white,
    matte_veil_strength,
    unmatte_over_white,
)

SPRITES = ROOT / "sprites"
VEIL_THRESHOLD = 0.01
"""Mean border alpha above this means a residual matte is present."""
APPEARANCE_TOLERANCE = 2.0
"""Max per-channel change over white a repair may introduce (out of 255)."""


def _plates(layer: str, only: str) -> list[Path]:
    paths = sorted((SPRITES / layer).glob("*.png"))
    if only:
        wanted = {k.strip() for k in only.split(",") if k.strip()}
        unknown = wanted - {p.stem for p in paths}
        if unknown:
            raise SystemExit(f"unknown plates in {layer}: {sorted(unknown)}")
        paths = [p for p in paths if p.stem in wanted]
    if not paths:
        raise SystemExit(f"no PNGs under sprites/{layer}")
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--layer", required=True)
    ap.add_argument("--only", default="", help="comma-separated plate stems")
    ap.add_argument("--unmatte", action="store_true",
                    help="rebuild straight alpha from ink-on-white and write back")
    ap.add_argument("--check", action="store_true",
                    help="report veil strength only; write nothing")
    args = ap.parse_args(argv)
    if not (args.unmatte or args.check):
        raise SystemExit("nothing to do: pass --check or --unmatte")

    plates = _plates(args.layer, args.only)
    width = max(len(p.stem) for p in plates)
    print(f"{'plate':<{width}}  {'veil':>6}  {'->':>6}  {'KB':>7}  {'->':>7}  "
          f"{'dmax':>5}  {'dmean':>6}")
    repaired = 0
    for path in plates:
        before = Image.open(path).convert("RGBA")
        veil0 = matte_veil_strength(before)
        kb0 = path.stat().st_size / 1024
        if not args.unmatte:
            flag = "  VEIL" if veil0 > VEIL_THRESHOLD else ""
            print(f"{path.stem:<{width}}  {veil0:6.4f}  {'':>6}  {kb0:7.0f}  "
                  f"{'':>7}  {'':>5}  {'':>6}{flag}")
            continue

        after = unmatte_over_white(before)
        dmax, dmean = appearance_delta_over_white(before, after)
        if dmax > APPEARANCE_TOLERANCE:
            print(f"{path.stem}: REFUSED — repair would change the plate over "
                  f"white by {dmax:.1f}/255 (limit {APPEARANCE_TOLERANCE})",
                  file=sys.stderr)
            return 1
        after.save(path, format="PNG", optimize=True)
        veil1 = matte_veil_strength(Image.open(path).convert("RGBA"))
        kb1 = path.stat().st_size / 1024
        repaired += 1
        print(f"{path.stem:<{width}}  {veil0:6.4f}  {veil1:6.4f}  {kb0:7.0f}  "
              f"{kb1:7.0f}  {dmax:5.1f}  {dmean:6.3f}")

    if args.unmatte:
        print(f"\nrepaired {repaired} plate(s) in sprites/{args.layer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
