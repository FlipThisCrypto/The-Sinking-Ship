# SPDX-License-Identifier: MIT
"""Generate the site's social-share (Open Graph / Twitter) card.

Deterministic, offline Pillow composite — no network, safe to re-run. Produces a
1200x630 branded card written to site/assets/og-image.png (and a .jpg fallback
for platforms that reject PNG OG images). The open-chest cutout already shipped
for the landing page is composited on a depth-gradient ground with the wordmark
and tagline, so shared links to any page render a real image card instead of a
blank preview.

Usage:
    python scripts/gen_og_image.py
    python scripts/gen_og_image.py --out site/assets/og-image.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent

# Brand palette (matches site/style.css tokens).
NAVY = (10, 14, 28)
HADAL = (18, 22, 52)
BONE = (244, 244, 240)
GOLD = (217, 154, 60)
AQUA = (56, 223, 232)
SLATE = (150, 164, 196)

W, H = 1200, 630
CHEST = ROOT / "site" / "assets" / "chest" / "open_chest-removebg.png"


def _fonts():
    """Prefer Arial (present on the dev host); degrade to Pillow's default."""
    for family in (("arialbd.ttf", "arial.ttf"), ("Arial_Bold.ttf", "Arial.ttf")):
        try:
            bold, reg = family
            return (
                ImageFont.truetype(bold, 88),
                ImageFont.truetype(reg, 34),
                ImageFont.truetype(bold, 30),
                ImageFont.truetype(reg, 26),
            )
        except OSError:
            continue
    d = ImageFont.load_default()
    return d, d, d, d


def _vertical_gradient(top: tuple, bottom: tuple) -> Image.Image:
    """Descend from surface-navy into hadal blue — the collection's motif."""
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        grad.putpixel((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return grad.resize((W, H))


def render(out: Path) -> None:
    img = _vertical_gradient(NAVY, HADAL)
    draw = ImageDraw.Draw(img, "RGBA")

    # Faint bubble column rising on the right — depth atmosphere, deterministic.
    for i, (bx, by, br, ba) in enumerate([
        (980, 470, 10, 40), (1010, 400, 6, 32), (955, 330, 8, 28),
        (1030, 250, 5, 22), (900, 210, 12, 26), (1060, 150, 7, 18),
    ]):
        draw.ellipse([bx - br, by - br, bx + br, by + br], outline=(*AQUA, ba), width=2)

    # Composite the open-chest cutout on the right with a soft aqua glow.
    if CHEST.exists():
        chest = Image.open(CHEST).convert("RGBA")
        target_h = 430
        scale = target_h / chest.height
        chest = chest.resize((round(chest.width * scale), target_h), Image.LANCZOS)
        cx, cy = W - chest.width - 70, H - chest.height - 60
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([cx - 20, cy + 60, cx + chest.width + 20, cy + chest.height + 40],
                   fill=(*AQUA, 60))
        img.paste(Image.alpha_composite(img.convert("RGBA"),
                                        glow.filter(ImageFilter.GaussianBlur(40))).convert("RGB"),
                  (0, 0))
        img.paste(chest, (cx, cy), chest)

    f_word, f_sub, f_tag, f_meta = _fonts()

    # Left column: wordmark, tagline, one-line pitch, credentials strip.
    draw.text((80, 120), "THE", fill=BONE, font=f_word)
    draw.text((80, 215), "SINKING", fill=BONE, font=f_word)
    draw.text((80, 310), "SHIP", fill=GOLD, font=f_word)
    draw.text((84, 424), "Hope never sinks.", fill=AQUA, font=f_sub)
    draw.text((84, 470),
              "44,444 hand-drawn salvage records on Chia.",
              fill=SLATE, font=f_meta)

    # Bottom credentials bar.
    draw.line([80, 540, W - 80, 540], fill=(*AQUA, 90), width=2)
    draw.text((80, 556), "BLIND MINT", fill=BONE, font=f_tag)
    draw.text((320, 556), "PROVABLY FAIR", fill=BONE, font=f_tag)
    draw.text((620, 556), "COMMIT – REVEAL", fill=BONE, font=f_tag)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    jpg = out.with_suffix(".jpg")
    img.save(jpg, "JPEG", quality=88)
    print(f"wrote {out} and {jpg} ({W}x{H})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the site social-share card.")
    ap.add_argument("--out", type=Path, default=ROOT / "site" / "assets" / "og-image.png")
    args = ap.parse_args()
    render(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
