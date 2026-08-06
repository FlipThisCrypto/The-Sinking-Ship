# SPDX-License-Identifier: MIT
"""Render a parameter sweep for pupil blanking on one body source plate.

The tuning loop is visual — a number cannot tell you whether an eye still reads
as the artist drew it — so this renders a labelled grid of candidate settings
against the original and leaves the judgement to a human (or an agent) looking
at the image.

Usage:
    python scripts/tune_blank.py --plate green_standing --out sweep.png
    python scripts/tune_blank.py --plate green_standing --out one.png \
        --feature-frac 0.34 --cut-pct 55 --cover 1.0 --single
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from PIL import Image, ImageDraw  # noqa: E402

from artgen import rig  # noqa: E402
from artgen.repair import blank_pupil  # noqa: E402

VAULT = ROOT / "vault" / "sprites-v1" / "body"

FEATURE_FRACS = (0.26, 0.34, 0.44)
CUT_PCTS = (40.0, 55.0, 70.0)


def crop_eye(img: Image.Image, anchor, zoom: float = 3.2) -> Image.Image:
    """Head-tight crop centred on the eye, padded so it never clips."""
    size = img.width
    pad = size
    big = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (255, 255, 255, 255))
    big.alpha_composite(img, (pad, pad))
    r = max(8.0, anchor.eye_w * size * zoom)
    cx, cy = anchor.eye_x * size + pad, anchor.eye_y * size + pad
    return big.crop((int(cx - r), int(cy - r), int(cx + r), int(cy + r))).convert("RGB")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plate", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--single", action="store_true",
                    help="render one setting rather than the grid")
    ap.add_argument("--feature-frac", type=float, default=0.34)
    ap.add_argument("--cut-pct", type=float, default=55.0)
    ap.add_argument("--cover", type=float, default=1.0)
    ap.add_argument("--seed-from", type=float, default=1.55)
    ap.add_argument("--zoom", type=float, default=3.2)
    ap.add_argument("--cell", type=int, default=340)
    args = ap.parse_args(argv)

    if args.plate not in rig.ANNOTATIONS:
        raise SystemExit(f"unknown plate {args.plate!r}; "
                         f"have {sorted(rig.ANNOTATIONS)}")
    anchor = rig.ANNOTATIONS[args.plate]
    src = Image.open(VAULT / f"{args.plate}.png").convert("RGBA")

    if args.single:
        panels = [("original", src),
                  (f"ff={args.feature_frac} cut={args.cut_pct} cover={args.cover}",
                   blank_pupil(src, anchor.eye_x, anchor.eye_y, anchor.eye_w,
                               feature_frac=args.feature_frac,
                               cut_pct=args.cut_pct, cover=args.cover,
                               seed_from=args.seed_from))]
        cols, rows = 2, 1
    else:
        panels = [("ORIGINAL", src)]
        for ff in FEATURE_FRACS:
            for cp in CUT_PCTS:
                panels.append((
                    f"ff={ff} cut={cp:.0f}",
                    blank_pupil(src, anchor.eye_x, anchor.eye_y, anchor.eye_w,
                                feature_frac=ff, cut_pct=cp, cover=args.cover,
                                seed_from=args.seed_from)))
        cols, rows = 5, 2

    cell, label = args.cell, 20
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label)), (250, 250, 246))
    draw = ImageDraw.Draw(sheet)
    for i, (name, img) in enumerate(panels):
        x, y = (i % cols) * cell, (i // cols) * (cell + label)
        sheet.paste(crop_eye(img, anchor, args.zoom).resize((cell, cell),
                                                            Image.LANCZOS),
                    (x, y + label))
        draw.text((x + 4, y + 4), name, fill=(15, 15, 15))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"{args.plate}: {len(panels)} panel(s) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
