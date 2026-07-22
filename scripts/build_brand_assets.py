# SPDX-License-Identifier: MIT
"""Derive web/marketplace-optimized brand assets from the owner's source art.

The owner supplies high-res banner + icon PNGs (multi-MB). This produces the
lean, correctly-sized derivatives the site and CHIP-0007 collection block
reference:

    site/assets/brand/icon.png    600x600   collection icon / apple-touch
    site/assets/brand/banner.png  1600x400  collection banner (4:1)
    site/assets/og-image.png      1200x630  social card (real art on dark ground)

Deterministic and offline. Re-run whenever the source art changes.

Usage:
    python scripts/build_brand_assets.py                     # sources in repo root
    python scripts/build_brand_assets.py --src-dir path/to/art
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
NAVY = (10, 14, 28)
BRAND = ROOT / "site" / "assets" / "brand"


def _open_rgb(path: Path) -> Image.Image:
    """Open and flatten onto the brand navy so no stray alpha ships."""
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (*NAVY, 255))
        im = Image.alpha_composite(bg, im)
    return im.convert("RGB")


def _cover_resize(im: Image.Image, w: int, h: int) -> Image.Image:
    """Scale + center-crop to exactly w x h (no distortion)."""
    scale = max(w / im.width, h / im.height)
    resized = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def build(
    src_dir: Path,
    brand_dir: Path | None = None,
    og_out: Path | None = None,
) -> list[Path]:
    target_brand = brand_dir or (ROOT / "site" / "assets" / "brand")
    target_og = og_out or (ROOT / "site" / "assets" / "og-image.png")

    icon_src = _open_rgb(src_dir / "icon.png")
    banner_src = _open_rgb(src_dir / "banner.png")
    target_brand.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []

    # Icon + banner are opaque illustrations — JPEG q90 is visually lossless at
    # these sizes and ~10x smaller than PNG, which matters for marketplace loads.
    icon = _cover_resize(icon_src, 600, 600)
    p = target_brand / "icon.jpg"
    icon.save(p, "JPEG", quality=90, optimize=True)
    out.append(p)

    banner = _cover_resize(banner_src, 1600, 400)
    p = target_brand / "banner.jpg"
    banner.save(p, "JPEG", quality=90, optimize=True)
    out.append(p)

    # Social card: the whole square icon composition on the brand ground, so
    # shared links show the real art at the 1.91:1 ratio OG/Twitter expect.
    og = Image.new("RGB", (1200, 630), NAVY)
    art = icon_src.copy()
    art.thumbnail((630, 630), Image.LANCZOS)
    og.paste(art, ((1200 - art.width) // 2, (630 - art.height) // 2))
    target_og.parent.mkdir(parents=True, exist_ok=True)
    og.save(target_og, "PNG", optimize=True)
    out.append(target_og)
    og.save(target_og.with_suffix(".jpg"), "JPEG", quality=88)
    out.append(target_og.with_suffix(".jpg"))

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build web/marketplace brand assets.")
    ap.add_argument("--src-dir", type=Path, default=ROOT,
                    help="directory holding source icon.png + banner.png")
    ap.add_argument("--brand-dir", type=Path, default=None)
    ap.add_argument("--og-out", type=Path, default=None)
    args = ap.parse_args()
    for p in build(args.src_dir, brand_dir=args.brand_dir, og_out=args.og_out):
        size = p.stat().st_size
        print(f"wrote {p} ({size // 1024} KB)")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
