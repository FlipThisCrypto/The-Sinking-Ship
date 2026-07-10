# SPDX-License-Identifier: MIT
"""Contact sheet for cohesion review (spec Phase 0: 'generate test outputs
and eyeball cohesion').

Rolls N NFTs through the real engine, renders them at thumbnail size, and
tiles them into one sheet with rarity labels — the fastest way to judge
whether the collection reads as one world.

Usage:
    python scripts/make_contact_sheet.py --count 24 --seed cohesion
    python scripts/make_contact_sheet.py --from-dir output/style_verify
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from shipgen.config import GenConfig  # noqa: E402
from shipgen.roll import RollEngine  # noqa: E402
import render_engine as re_mod  # noqa: E402

log = logging.getLogger("make_contact_sheet")
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=24)
    ap.add_argument("--seed", default="cohesion")
    ap.add_argument("--cell", type=int, default=384)
    ap.add_argument("--from-dir", type=Path, default=None,
                    help="tile existing renders instead of rolling fresh ones")
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "contact_sheet.png")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    tiles: list[tuple[Image.Image, str]] = []
    if args.from_dir:
        for p in sorted(args.from_dir.glob("*.png"))[: args.count]:
            tiles.append((Image.open(p).convert("RGBA"), p.stem))
    else:
        cfg = GenConfig()
        engine = RollEngine(cfg)
        palette = re_mod.Palette()
        profile = re_mod.load_profile(None)
        store = re_mod.SpriteStore(cfg, palette, profile)
        zones = cfg.tiers_doc["depth_zones"]
        salt = hashlib.sha256(f"contact:{args.seed}".encode()).digest()
        for i in range(args.count):
            nft = engine.roll_nft(salt, f"sheet/{i}")
            zone = zones[i % len(zones)]
            img = re_mod.compose(store, nft.traits, zone)
            tiles.append((img, f"{nft.rarity_tier} · {zone}"))
            log.info("rolled %d/%d (%s, %s)", i + 1, args.count, nft.rarity_tier, zone)

    if not tiles:
        log.error("nothing to tile")
        return 1

    cols = math.ceil(math.sqrt(len(tiles)))
    rows = math.ceil(len(tiles) / cols)
    cell, label_h = args.cell, 26
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (244, 244, 240))
    d = ImageDraw.Draw(sheet)
    for i, (img, label) in enumerate(tiles):
        r, c = divmod(i, cols)
        thumb = img.resize((cell, cell), Image.LANCZOS).convert("RGB")
        y = r * (cell + label_h)
        sheet.paste(thumb, (c * cell, y))
        d.text((c * cell + 8, y + cell + 5), label, fill=(60, 60, 80))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    log.info("contact sheet: %d tiles -> %s (%dx%d)", len(tiles), args.out,
             sheet.width, sheet.height)
    return 0


if __name__ == "__main__":
    sys.exit(main())
