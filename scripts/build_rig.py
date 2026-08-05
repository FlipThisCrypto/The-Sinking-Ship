# SPDX-License-Identifier: MIT
"""Write config/rig.json and prove the head anchors are where they claim to be.

The anchors in ``engine/artgen/rig.py`` are hand-annotated from the art. This
script is how they are checked: ``--sheet`` draws each recorded anchor on its
plate as a crosshair and head box, so a wrong entry is obvious at a glance.
Two automatic detectors were tried first and discarded (see rig.py) — with
twelve unique images, annotate-and-verify beats detect-and-hope.

Usage:
    python scripts/build_rig.py --sheet output/art/rig_proof.png
    python scripts/build_rig.py --write
    python scripts/build_rig.py --registration output/art/rig_registration.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from artgen import rig  # noqa: E402

SPRITES = ROOT / "sprites"


def _target_card(size: int):
    """A registration card authored against the canonical rig.

    Crosshair on the canonical eye point, a box the size of the canonical head,
    and a hat band above it — exactly the geometry a real eyes/hat sprite would
    occupy. If this lands on the head for all 48 bodies, so will the art.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = rig.CANONICAL
    ex, ey, h = c.eye_x * size, c.eye_y * size, c.head_h * size
    w = h * 0.78
    d.rectangle([ex - w / 2, ey - h * 0.5, ex + w / 2, ey + h * 0.5],
                outline=(220, 40, 60, 255), width=max(2, size // 300))
    d.line([(ex - w * 0.8, ey), (ex + w * 0.8, ey)], fill=(30, 120, 220, 255),
           width=max(2, size // 340))
    d.line([(ex, ey - h * 0.7), (ex, ey + h * 0.7)], fill=(30, 120, 220, 255),
           width=max(2, size // 340))
    d.ellipse([ex - h * 0.09, ey - h * 0.09, ex + h * 0.09, ey + h * 0.09],
              outline=(30, 120, 220, 255), width=max(2, size // 340))
    d.rectangle([ex - w * 0.62, ey - h * 0.62, ex + w * 0.62, ey - h * 0.42],
                outline=(240, 160, 20, 255), width=max(2, size // 320))
    return img


def proof_sheet(path: Path, cols: int = 6, cell: int = 330) -> None:
    """Every plate with its recorded anchor drawn on it."""
    from PIL import Image, ImageDraw

    items = sorted(rig.ANNOTATIONS.items())
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (250, 250, 246))
    draw = ImageDraw.Draw(sheet)
    for i, (name, a) in enumerate(items):
        src = Image.open(ROOT / "vault" / "sprites-v1" / "body" / f"{name}.png")
        tile = Image.new("RGBA", src.size, (255, 255, 255, 255))
        tile.alpha_composite(src.convert("RGBA"))
        ox, oy = (i % cols) * cell, (i // cols) * cell
        sheet.paste(tile.convert("RGB").resize((cell, cell), Image.LANCZOS), (ox, oy))
        ex, ey, h = a.eye_x * cell, a.eye_y * cell, a.head_h * cell
        w = h * 0.78
        draw.rectangle([ox + ex - w / 2, oy + ey - h / 2,
                        ox + ex + w / 2, oy + ey + h / 2],
                       outline=(220, 40, 60), width=2)
        draw.line([(ox + ex - w * 0.75, oy + ey), (ox + ex + w * 0.75, oy + ey)],
                  fill=(30, 120, 220), width=2)
        draw.line([(ox + ex, oy + ey - h * 0.6), (ox + ex, oy + ey + h * 0.6)],
                  fill=(30, 120, 220), width=2)
        draw.text((ox + 4, oy + 4), name, fill=(20, 20, 20))
        draw.text((ox + 4, oy + 15), f"{a.facing}  h={a.head_h:.3f}", fill=(110, 110, 110))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    print(f"anchor proof sheet -> {path}")


def registration_sheet(path: Path, cols: int = 8, cell: int = 260) -> None:
    """The canonical registration card transformed onto all 48 body plates."""
    from PIL import Image, ImageDraw

    card = _target_card(cell)
    anchors = rig.plate_anchors()
    names = sorted(anchors)
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (250, 250, 246))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        src = Image.open(SPRITES / "body" / f"{name}.png").convert("RGBA")
        tile = Image.new("RGBA", (cell, cell), (255, 255, 255, 255))
        tile.alpha_composite(src.resize((cell, cell), Image.LANCZOS))
        tile.alpha_composite(rig.apply_face_transform(card, anchors[name], cell))
        ox, oy = (i % cols) * cell, (i // cols) * cell
        sheet.paste(tile.convert("RGB"), (ox, oy))
        draw.text((ox + 3, oy + 3), name, fill=(20, 20, 20))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    print(f"registration sheet -> {path}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--registration", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    if not any((args.sheet, args.registration, args.write, args.report)):
        args.report = True

    if args.report:
        print(f"canonical: {rig.CANONICAL}")
        width = max(len(n) for n in rig.ANNOTATIONS)
        print(f"{'source':<{width}}  {'eye_x':>6} {'eye_y':>6} {'head_h':>7} "
              f"{'facing':>6}  {'scale':>6} {'dx':>7} {'dy':>7}")
        for name, a in sorted(rig.ANNOTATIONS.items()):
            sc, dx, dy, mirror = rig.face_transform(a)
            print(f"{name:<{width}}  {a.eye_x:6.3f} {a.eye_y:6.3f} {a.head_h:7.3f} "
                  f"{a.facing:>6}  {sc:6.3f} {dx:7.3f} {dy:7.3f}"
                  f"{'  mirrored' if mirror else ''}")
        scales = [rig.face_transform(a)[0] for a in rig.ANNOTATIONS.values()]
        print(f"\nscale range {min(scales):.2f}x .. {max(scales):.2f}x")

    if args.sheet:
        proof_sheet(Path(args.sheet))
    if args.registration:
        registration_sheet(Path(args.registration))
    if args.write:
        out = rig.write_rig()
        print(f"wrote {out.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
