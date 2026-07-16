# SPDX-License-Identifier: MIT
"""Generate a shareable "I struck [rarity] at [depth]" PNG (P8 share card).

Offline Pillow card — no network. Safe for mint-day social posts.

Usage:
    python scripts/gen_share_card.py --rarity legendary --zone hadal --out output/share.png
    python scripts/gen_share_card.py --from-manifest site/demo_chest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent

# Zone accent from palette moods (soft guide; not a full render)
ZONE_BG = {
    "surface": (200, 50, 63),
    "sunlight": (217, 154, 60),
    "twilight": (122, 74, 168),
    "midnight": (58, 95, 158),
    "abyssal": (38, 64, 122),
    "hadal": (20, 24, 58),
}
RARITY_COLOR = {
    "common": (138, 138, 158),
    "uncommon": (111, 146, 196),
    "rare": (56, 223, 232),
    "epic": (122, 74, 168),
    "legendary": (217, 154, 60),
    "mythic": (227, 93, 91),
    "grail": (236, 200, 115),
}


def _best_rarity(manifest: dict) -> str:
    rank = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3,
            "legendary": 4, "mythic": 5, "grail": 6}
    best, score = "common", -1
    for e in manifest.get("nfts", []):
        if e.get("type") == "grail":
            r = "grail"
        else:
            r = e.get("rarity_tier", "common")
        if rank.get(r, 0) > score:
            best, score = r, rank.get(r, 0)
    return best


def render_card(rarity: str, zone: str, qty: int | None, out: Path) -> None:
    w, h = 1200, 630
    bg = ZONE_BG.get(zone, (10, 14, 28))
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    # bone panel
    draw.rectangle([48, 48, w - 48, h - 48], outline=(244, 244, 240), width=3)
    accent = RARITY_COLOR.get(rarity, (244, 244, 240))
    draw.rectangle([48, h - 120, w - 48, h - 48], fill=accent)

    try:
        font_lg = ImageFont.truetype("arial.ttf", 54)
        font_md = ImageFont.truetype("arial.ttf", 36)
        font_sm = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font_lg = font_md = font_sm = ImageFont.load_default()

    title = "THE SINKING SHIP"
    draw.text((80, 80), title, fill=(244, 244, 240), font=font_md)
    line = f"I struck {rarity.upper()} at {zone} depth."
    draw.text((80, 200), line, fill=(244, 244, 240), font=font_lg)
    if qty is not None:
        draw.text((80, 280), f"Chest salvage: {qty}", fill=(200, 210, 230), font=font_sm)
    draw.text((80, h - 100), "Hope never sinks.", fill=(10, 14, 28), font=font_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    print(f"wrote {out}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rarity", default="rare")
    ap.add_argument("--zone", default="midnight")
    ap.add_argument("--qty", type=int, default=None)
    ap.add_argument("--from-manifest", default=None)
    ap.add_argument("--out", default=str(ROOT / "output" / "share_card.png"))
    args = ap.parse_args()

    rarity, zone, qty = args.rarity, args.zone, args.qty
    if args.from_manifest:
        m = json.loads(Path(args.from_manifest).read_text(encoding="utf-8"))
        rarity = _best_rarity(m)
        zone = m.get("zone", zone)
        qty = m.get("quantity", qty)
    render_card(rarity, zone, qty, Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
