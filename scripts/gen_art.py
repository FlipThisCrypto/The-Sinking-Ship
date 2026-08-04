# SPDX-License-Identifier: MIT
"""Author production sprite layers with engine/artgen.

Unlike ``gen_placeholder_sprites.py`` (which emits stand-ins), this writes the
**final** art for a layer. Output is deterministic: the same layer regenerated
twice produces byte-identical PNGs.

Usage:
    python scripts/gen_art.py --layer sky
    python scripts/gen_art.py --layer sky --only aurora,fire_sky --size 512
    python scripts/gen_art.py --layer sky --sheet output/art/sky_sheet.png
    python scripts/gen_art.py --layer sky --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from artgen import MASTER_PX, save_sprite  # noqa: E402
from artgen.core import alpha_stats, unique_colors  # noqa: E402

SPRITES = ROOT / "sprites"
CONFIG = ROOT / "config"

# layer name -> module exposing render(key, size) and all_keys()
RENDERERS = {
    "sky": "artgen.sky",
    "sea": "artgen.sea",
}


def _load(layer: str):
    import importlib

    if layer not in RENDERERS:
        raise SystemExit(
            f"no artgen renderer for layer {layer!r}; have: {', '.join(RENDERERS)}"
        )
    return importlib.import_module(RENDERERS[layer])


def expected_filenames(layer: str) -> list[str]:
    """Sprite filenames traits.json requires for ``layer`` (excludes None traits)."""
    doc = json.loads((CONFIG / "traits.json").read_text(encoding="utf-8"))
    for entry in doc["layers"]:
        if entry["name"] == layer:
            return [t["sprite_filename"] for t in entry["traits"]
                    if t.get("sprite_filename")]
    raise SystemExit(f"layer {layer!r} not present in traits.json")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--layer", required=True, choices=sorted(RENDERERS))
    ap.add_argument("--only", default="", help="comma-separated trait keys")
    ap.add_argument("--size", type=int, default=MASTER_PX)
    ap.add_argument("--out", default=None, help="output dir (default sprites/<layer>)")
    ap.add_argument("--sheet", default=None, help="also write a contact sheet here")
    ap.add_argument("--dry-run", action="store_true",
                    help="render and report, write nothing")
    args = ap.parse_args(argv)

    mod = _load(args.layer)
    keys = mod.all_keys()
    if args.only:
        wanted = [k.strip() for k in args.only.split(",") if k.strip()]
        unknown = [k for k in wanted if k not in keys]
        if unknown:
            raise SystemExit(f"unknown trait keys for {args.layer}: {unknown}")
        keys = wanted

    # Contract check: renderer keys must match traits.json exactly.
    required = {Path(f).stem for f in expected_filenames(args.layer)}
    have = set(mod.all_keys())
    if have != required:
        missing = sorted(required - have)
        extra = sorted(have - required)
        raise SystemExit(
            f"{args.layer} renderer/traits.json mismatch — missing {missing}, extra {extra}"
        )

    out_dir = Path(args.out) if args.out else SPRITES / args.layer
    total = 0
    rows: list[tuple[str, int, dict[str, float], int, float]] = []
    images = {}
    for key in keys:
        t0 = time.perf_counter()
        canvas = mod.render(key, size=args.size)
        img = canvas.to_image()
        images[key] = img
        stats = alpha_stats(img)
        colors = unique_colors(img)
        nbytes = 0
        if not args.dry_run:
            nbytes = save_sprite(img, out_dir / f"{key}.png", size=args.size)
            total += nbytes
        rows.append((key, nbytes, stats, colors, time.perf_counter() - t0))

    width = max(len(k) for k in keys)
    print(f"{'trait':<{width}}  {'KB':>7}  {'cover':>6}  {'meanA':>6}  "
          f"{'maxA':>5}  {'colors':>6}  {'sec':>5}")
    for key, nbytes, stats, colors, secs in rows:
        print(f"{key:<{width}}  {nbytes / 1024:7.0f}  {stats['coverage']:6.3f}  "
              f"{stats['mean']:6.3f}  {stats['max']:5.2f}  {colors:6d}  {secs:5.1f}")
    if not args.dry_run:
        print(f"\n{len(rows)} plates -> {out_dir.relative_to(ROOT).as_posix()} "
              f"({total / 1048576:.1f} MB total, "
              f"{total / max(1, len(rows)) / 1024:.0f} KB mean)")

    if args.sheet:
        _contact_sheet(images, Path(args.sheet), args.layer)
    return 0


def _contact_sheet(images: dict, path: Path, layer: str) -> None:
    """Composite each plate over bone-white so it is judged as it will render."""
    from PIL import Image, ImageDraw

    from artgen import BONE_WHITE

    cell, pad, label = 320, 10, 22
    cols = min(5, max(1, len(images)))
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cell + pad) + pad,
                              rows * (cell + pad + label) + pad), (26, 26, 32))
    draw = ImageDraw.Draw(sheet)
    for i, (key, img) in enumerate(images.items()):
        tile = Image.new("RGBA", (cell, cell), (*BONE_WHITE, 255))
        tile.alpha_composite(img.resize((cell, cell), Image.LANCZOS))
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + pad + label)
        sheet.paste(tile.convert("RGB"), (x, y))
        draw.text((x + 2, y + cell + 4), f"{layer}/{key}", fill=(210, 210, 220))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    print(f"contact sheet -> {path}")


if __name__ == "__main__":
    raise SystemExit(main())
