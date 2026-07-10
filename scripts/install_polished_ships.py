# SPDX-License-Identifier: MIT
"""Install polished Amano ship art into sprites/ + ship-only showcase.

Converts source illustrations (ships_amano refs and image-edit polish)
to 2048×2048 RGBA PNGs with near-white ground made transparent, then
writes:

  sprites/ship_class/<trait>.png   — full ship composition (ship-only art)
  output/style_loop/ship_<name>.png — bone-white showcase composites

Also emits empty transparent placeholders for character layers when
--blank-characters is set (default), so layered composites stay ship-only.

Usage:
    python scripts/install_polished_ships.py
    python scripts/install_polished_ships.py --manifest output/amano_polish/manifest.json
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("install_polished_ships")

MASTER = 2048
BONE = (244, 244, 240, 255)

# Default map: trait filename → ordered candidate source paths (first hit wins).
# Prefer authentic ships_amano refs; fall back to polish edits.
DEFAULT_MAP: dict[str, list[str]] = {
    "battleship.png": [
        "ships_amano/battleship_1.png",
        "output/amano_polish/battleship_crystal.jpg",
    ],
    "aircraft_carrier.png": [
        "output/amano_polish/aircraft_carrier_nochar.jpg",
        "ships_amano/aircraft_carrier_2.png",
        "ships_amano/aircraft_carrier_3.png",
    ],
    "blockchain_ship.png": [
        "ships_amano/blockchain_ship_1.png",
        "output/amano_polish/blockchain_ship.jpg",
    ],
    "pirate_ship.png": [
        "output/amano_polish/pirate_ship_nochar.jpg",
        "docs/art-reference/pirate-ship/pirate_ship_1.png",
        "output/amano_polish/pirate_ship.jpg",
    ],
    "cruiser.png": ["output/amano_polish/cruiser.jpg"],
    "submarine.png": ["output/amano_polish/submarine.jpg"],
    "ghost_ship.png": ["output/amano_polish/ghost_ship.jpg"],
    "wizard_ship.png": ["output/amano_polish/wizard_ship.jpg"],
    "the_ark.png": ["output/amano_polish/the_ark.jpg"],
    "cargo_ship.png": ["output/amano_polish/cargo_ship.jpg"],
    "luxury_yacht.png": ["output/amano_polish/luxury_yacht.jpg"],
    "steam_ship.png": ["output/amano_polish/steam_ship.jpg"],
    "fishing_boat.png": ["output/amano_polish/fishing_boat.jpg"],
    "tug_boat.png": ["output/amano_polish/tug_boat.jpg"],
    "lifeboat.png": ["output/amano_polish/lifeboat.jpg"],
    "raft.png": ["output/amano_polish/raft.jpg"],
}

# Layers that must stay empty for ship-only presentation
CHARACTER_LAYERS = ("body", "clothing", "eyes", "mouth", "hat", "aura")


def white_to_alpha(img: Image.Image, threshold: int = 248, soft: int = 12) -> Image.Image:
    """Near-white ground → transparent; soft edge for AA (vectorized)."""
    import numpy as np

    img = img.convert("RGBA")
    if img.size != (MASTER, MASTER):
        img = img.resize((MASTER, MASTER), Image.LANCZOS)
    arr = np.asarray(img).astype(np.float32)
    rgb = arr[:, :, :3]
    a = arr[:, :, 3]
    mn = rgb.min(axis=2)
    mx = rgb.max(axis=2)
    # pure white ground
    pure = (mx >= threshold) & (mn >= threshold - 20)
    # soft fringe
    fringe = (~pure) & (mx >= threshold - soft)
    t = (threshold - mx) / max(1, soft)
    t = np.clip(t, 0.0, 1.0)
    new_a = a.copy()
    new_a[pure] = 0
    new_a[fringe] = a[fringe] * t[fringe]
    out = np.dstack([rgb, new_a]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def to_bone_showcase(ship_rgba: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", (MASTER, MASTER), BONE)
    canvas.alpha_composite(ship_rgba)
    return canvas


def blank_layer(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0)).save(path, optimize=True)


def resolve(candidates: list[str]) -> Path | None:
    for c in candidates:
        p = ROOT / c
        if p.exists():
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=None,
                    help="optional JSON override {filename: [candidates...]}")
    ap.add_argument("--no-blank-characters", action="store_true")
    ap.add_argument("--showcase-dir", type=Path,
                    default=ROOT / "output" / "style_loop")
    ap.add_argument("--threshold", type=int, default=248)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    mapping = DEFAULT_MAP
    if args.manifest and args.manifest.exists():
        mapping = json.loads(args.manifest.read_text(encoding="utf-8"))

    ship_dir = ROOT / "sprites" / "ship_class"
    ship_dir.mkdir(parents=True, exist_ok=True)
    args.showcase_dir.mkdir(parents=True, exist_ok=True)

    installed = missing = 0
    for fname, cands in mapping.items():
        src = resolve(cands)
        if src is None:
            log.warning("MISSING source for %s (tried %s)", fname, cands)
            missing += 1
            continue
        log.info("%s <- %s", fname, src.relative_to(ROOT))
        rgba = white_to_alpha(Image.open(src), threshold=args.threshold)
        out = ship_dir / fname
        rgba.save(out, optimize=True)
        # also bone-white showcase (what humans should review)
        show = to_bone_showcase(rgba)
        show_name = f"ship_{Path(fname).stem}_2048.png"
        show.save(args.showcase_dir / show_name, optimize=True)
        # smaller preview
        show.resize((512, 512), Image.LANCZOS).save(
            args.showcase_dir / f"ship_{Path(fname).stem}_512.png", optimize=True,
        )
        installed += 1

    if not args.no_blank_characters:
        # blank all character-related sprites so layered samples stay ship-only
        cfg_path = ROOT / "config" / "traits.json"
        # minimal: blank every png under character layers
        for layer in CHARACTER_LAYERS:
            ldir = ROOT / "sprites" / layer
            if not ldir.exists():
                continue
            for png in ldir.glob("*.png"):
                blank_layer(png)
            log.info("blanked character layer %s", layer)
        # also blank scene overlays that fight full-composition ships
        for layer in ("scene_element", "ship_condition"):
            ldir = ROOT / "sprites" / layer
            if not ldir.exists():
                continue
            for png in ldir.glob("*.png"):
                blank_layer(png)
            log.info("blanked overlay layer %s", layer)
        # sky + sea transparent so full ship composition owns the frame
        for layer in ("sky", "sea"):
            ldir = ROOT / "sprites" / layer
            if not ldir.exists():
                continue
            for png in ldir.glob("*.png"):
                blank_layer(png)
            log.info("blanked atmosphere layer %s", layer)

    # contact sheet of showcases
    previews = sorted(args.showcase_dir.glob("ship_*_512.png"))
    if previews:
        cols = 4
        rows = (len(previews) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 512, rows * 512), (244, 244, 240))
        for i, p in enumerate(previews):
            im = Image.open(p).convert("RGB")
            sheet.paste(im, ((i % cols) * 512, (i // cols) * 512))
        sheet.save(args.showcase_dir / "contact_ships.jpg", quality=92)
        log.info("contact sheet -> %s", args.showcase_dir / "contact_ships.jpg")

    log.info("installed %d ship(s), %d missing", installed, missing)
    return 1 if missing and installed == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
