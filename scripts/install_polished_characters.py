# SPDX-License-Identifier: MIT
"""Install polished Tom Bepe / Amano character plates into sprites + showcase.

Character-only art (no ships). Sources live in output/amano_polish/characters/
and docs/art-reference/tom-bepe-amano/.

Writes:
  sprites/body/<variant>_<pose>.png  — for known body×pose combos
  output/style_loop/char_*.png       — bone-white showcases
  output/style_loop/contact_chars.jpg

Usage:
    python scripts/install_polished_characters.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("install_polished_characters")

MASTER = 2048
BONE = (244, 244, 240, 255)
CHAR_DIR = ROOT / "output" / "amano_polish" / "characters"
SHOW_DIR = ROOT / "output" / "style_loop"
BODY_DIR = ROOT / "sprites" / "body"

# Map body sprite filenames → ordered candidate sources (first hit wins).
# Pattern: {body}_{pose}.png per traits.json sprite_pattern.
DEFAULT_MAP: dict[str, list[str]] = {
    # Green (default hero) × poses
    "green_standing.png": [
        "output/amano_polish/characters/hero_front_green.jpg",
        "output/amano_polish/characters/hero_standing_smoke.jpg",
        "docs/art-reference/tom-bepe-amano/tom_bepe_amano_3.png",
    ],
    "green_saluting.png": ["output/amano_polish/characters/pose_saluting.jpg"],
    "green_sitting.png": ["output/amano_polish/characters/pose_sitting.jpg"],
    "green_on_bow.png": ["output/amano_polish/characters/pose_on_bow.jpg"],
    "green_back_turned.png": ["output/amano_polish/characters/pose_back_turned.jpg"],
    "green_looking_down.png": ["output/amano_polish/characters/pose_looking_down.jpg"],
    # Blue
    "blue_standing.png": [
        "output/amano_polish/characters/variant_blue.jpg",
        "output/amano_polish/characters/hero_standing_smoke.jpg",
    ],
    "blue_saluting.png": ["output/amano_polish/characters/pose_saluting.jpg"],
    "blue_sitting.png": ["output/amano_polish/characters/pose_sitting.jpg"],
    "blue_on_bow.png": ["output/amano_polish/characters/pose_on_bow.jpg"],
    "blue_back_turned.png": ["output/amano_polish/characters/pose_back_turned.jpg"],
    "blue_looking_down.png": ["output/amano_polish/characters/pose_looking_down.jpg"],
    # Gold
    "gold_standing.png": ["output/amano_polish/characters/variant_gold.jpg"],
    "gold_saluting.png": ["output/amano_polish/characters/variant_gold.jpg"],
    "gold_sitting.png": ["output/amano_polish/characters/variant_gold.jpg"],
    "gold_on_bow.png": ["output/amano_polish/characters/variant_gold.jpg"],
    "gold_back_turned.png": ["output/amano_polish/characters/variant_gold.jpg"],
    "gold_looking_down.png": ["output/amano_polish/characters/variant_gold.jpg"],
    # Ghost
    "ghost_standing.png": ["output/amano_polish/characters/variant_ghost.jpg"],
    "ghost_saluting.png": ["output/amano_polish/characters/variant_ghost.jpg"],
    "ghost_sitting.png": ["output/amano_polish/characters/variant_ghost.jpg"],
    "ghost_on_bow.png": ["output/amano_polish/characters/variant_ghost.jpg"],
    "ghost_back_turned.png": ["output/amano_polish/characters/variant_ghost.jpg"],
    "ghost_looking_down.png": ["output/amano_polish/characters/variant_ghost.jpg"],
    # Chrome
    "chrome_standing.png": ["output/amano_polish/characters/variant_chrome.jpg"],
    "chrome_saluting.png": ["output/amano_polish/characters/variant_chrome.jpg"],
    "chrome_sitting.png": ["output/amano_polish/characters/variant_chrome.jpg"],
    "chrome_on_bow.png": ["output/amano_polish/characters/variant_chrome.jpg"],
    "chrome_back_turned.png": ["output/amano_polish/characters/variant_chrome.jpg"],
    "chrome_looking_down.png": ["output/amano_polish/characters/variant_chrome.jpg"],
    # Corrupted
    "corrupted_standing.png": ["output/amano_polish/characters/variant_corrupted.jpg"],
    "corrupted_saluting.png": ["output/amano_polish/characters/variant_corrupted.jpg"],
    "corrupted_sitting.png": ["output/amano_polish/characters/variant_corrupted.jpg"],
    "corrupted_on_bow.png": ["output/amano_polish/characters/variant_corrupted.jpg"],
    "corrupted_back_turned.png": ["output/amano_polish/characters/variant_corrupted.jpg"],
    "corrupted_looking_down.png": ["output/amano_polish/characters/variant_corrupted.jpg"],
    # Emerald ~ green hero
    "emerald_standing.png": [
        "output/amano_polish/characters/hero_no_smoke.jpg",
        "docs/art-reference/tom-bepe-amano/tom_bepe_no_smoke_1.png",
    ],
    "emerald_saluting.png": ["output/amano_polish/characters/pose_saluting.jpg"],
    "emerald_sitting.png": ["output/amano_polish/characters/pose_sitting.jpg"],
    "emerald_on_bow.png": ["output/amano_polish/characters/pose_on_bow.jpg"],
    "emerald_back_turned.png": ["output/amano_polish/characters/pose_back_turned.jpg"],
    "emerald_looking_down.png": ["output/amano_polish/characters/pose_looking_down.jpg"],
    # Zombie ~ muted green
    "zombie_standing.png": [
        "output/amano_polish/characters/hero_front_green.jpg",
    ],
    "zombie_saluting.png": ["output/amano_polish/characters/pose_saluting.jpg"],
    "zombie_sitting.png": ["output/amano_polish/characters/pose_sitting.jpg"],
    "zombie_on_bow.png": ["output/amano_polish/characters/pose_on_bow.jpg"],
    "zombie_back_turned.png": ["output/amano_polish/characters/pose_back_turned.jpg"],
    "zombie_looking_down.png": ["output/amano_polish/characters/pose_looking_down.jpg"],
}

# Named showcase plates (not necessarily every body combo)
SHOWCASE: list[tuple[str, str]] = [
    ("hero_standing_smoke", "output/amano_polish/characters/hero_standing_smoke.jpg"),
    ("hero_looking_up", "output/amano_polish/characters/hero_looking_up.jpg"),
    ("hero_front_green", "output/amano_polish/characters/hero_front_green.jpg"),
    ("hero_no_smoke", "output/amano_polish/characters/hero_no_smoke.jpg"),
    ("pose_saluting", "output/amano_polish/characters/pose_saluting.jpg"),
    ("pose_looking_down", "output/amano_polish/characters/pose_looking_down.jpg"),
    ("pose_sitting", "output/amano_polish/characters/pose_sitting.jpg"),
    ("pose_back_turned", "output/amano_polish/characters/pose_back_turned.jpg"),
    ("pose_on_bow", "output/amano_polish/characters/pose_on_bow.jpg"),
    ("variant_gold", "output/amano_polish/characters/variant_gold.jpg"),
    ("variant_ghost", "output/amano_polish/characters/variant_ghost.jpg"),
    ("variant_blue", "output/amano_polish/characters/variant_blue.jpg"),
    ("variant_chrome", "output/amano_polish/characters/variant_chrome.jpg"),
    ("variant_corrupted", "output/amano_polish/characters/variant_corrupted.jpg"),
    ("ref_amano_1", "docs/art-reference/tom-bepe-amano/tom_bepe_amano_1.png"),
    ("ref_no_smoke_1", "docs/art-reference/tom-bepe-amano/tom_bepe_no_smoke_1.png"),
]


def white_to_alpha(img: Image.Image, threshold: int = 248, soft: int = 12) -> Image.Image:
    img = img.convert("RGBA")
    if img.size != (MASTER, MASTER):
        img = img.resize((MASTER, MASTER), Image.LANCZOS)
    arr = np.asarray(img).astype(np.float32)
    rgb, a = arr[:, :, :3], arr[:, :, 3]
    mn, mx = rgb.min(axis=2), rgb.max(axis=2)
    pure = (mx >= threshold) & (mn >= threshold - 20)
    fringe = (~pure) & (mx >= threshold - soft)
    t = np.clip((threshold - mx) / max(1, soft), 0.0, 1.0)
    new_a = a.copy()
    new_a[pure] = 0
    new_a[fringe] = a[fringe] * t[fringe]
    return Image.fromarray(np.dstack([rgb, new_a]).astype(np.uint8), "RGBA")


def to_bone(rgba: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", (MASTER, MASTER), BONE)
    canvas.alpha_composite(rgba)
    return canvas


def resolve(cands: list[str]) -> Path | None:
    for c in cands:
        p = ROOT / c
        if p.exists():
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", type=int, default=248)
    ap.add_argument("--sprites-only", action="store_true")
    ap.add_argument("--showcase-only", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    SHOW_DIR.mkdir(parents=True, exist_ok=True)
    BODY_DIR.mkdir(parents=True, exist_ok=True)

    installed = missing = 0
    if not args.showcase_only:
        for fname, cands in DEFAULT_MAP.items():
            src = resolve(cands)
            if src is None:
                log.warning("MISSING %s", fname)
                missing += 1
                continue
            log.info("body/%s <- %s", fname, src.relative_to(ROOT))
            rgba = white_to_alpha(Image.open(src), threshold=args.threshold)
            rgba.save(BODY_DIR / fname, optimize=True)
            installed += 1

    if not args.sprites_only:
        previews: list[Path] = []
        for name, rel in SHOWCASE:
            src = ROOT / rel
            if not src.exists():
                log.warning("showcase missing %s", rel)
                continue
            rgba = white_to_alpha(Image.open(src), threshold=args.threshold)
            show = to_bone(rgba)
            p2048 = SHOW_DIR / f"char_{name}_2048.png"
            p512 = SHOW_DIR / f"char_{name}_512.png"
            show.save(p2048, optimize=True)
            show.resize((512, 512), Image.LANCZOS).save(p512, optimize=True)
            previews.append(p512)
            log.info("showcase %s", name)

        if previews:
            cols = 4
            rows = (len(previews) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * 512, rows * 512), (244, 244, 240))
            for i, p in enumerate(previews):
                sheet.paste(Image.open(p).convert("RGB"),
                            ((i % cols) * 512, (i // cols) * 512))
            sheet.save(SHOW_DIR / "contact_chars.jpg", quality=92)
            log.info("contact sheet -> %s", SHOW_DIR / "contact_chars.jpg")

    log.info("body sprites installed: %d (missing %d)", installed, missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
