# SPDX-License-Identifier: MIT
"""Generate PLACEHOLDER sprites + per-layer READMEs from traits.json (P4).

Two renderers, chosen by render profile (config/render.json):

  pixel        — the original 48x48 solid-block placeholders (kept verbatim).
  illustration — evocative stand-ins in the ART-DIRECTION.md spirit:
                 vertical gradients that sink into deep navy, ship and
                 character silhouettes, wave / smoke / aura flourishes, all
                 anti-aliased (drawn 2x supersampled, LANCZOS downscaled).
                 Deterministic per trait (sha256 of the sprite key), colours
                 drawn from the v2 master palette with keyword-driven moods.

They are still unmistakably placeholders (each sprite carries a small
corner checker tag, and every layer README says so) — but composites now
read as moody gradient posters instead of colour blocks, so sample renders
and contact sheets are presentable while the real Amano art is produced.

Usage:
    python scripts/gen_placeholder_sprites.py [--force] [--profile pixel|illustration]
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

from shipgen.config import GenConfig, load_json, CONFIG_DIR  # noqa: E402

log = logging.getLogger("gen_placeholder_sprites")
ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "sprites"

PX_PIXEL = 48
SS = 2  # illustration supersample factor

# ---------------------------------------------------------------- palette

_PALETTE = {c["name"]: tuple(int(c["hex"][i:i + 2], 16) for i in (1, 3, 5))
            for c in load_json(CONFIG_DIR / "palette.json")["master"]}

POOLS = {
    "crimson": ["crimson", "blood_red", "maroon", "ember_orange", "coral"],
    "gold": ["gold", "amber", "pale_gold", "sand", "bronze"],
    "green": ["chia_green", "bright_green", "teal_green", "pale_green", "deep_teal"],
    "violet": ["deep_violet", "violet", "amethyst", "lavender"],
    "blue": ["sea_blue", "steel_blue", "pale_blue", "navy"],
    "dark": ["shadow_navy", "deep_ink", "abyss_navy", "deep_navy", "ink_black"],
    "pale": ["bone_white", "ash_gray", "pale_blue", "slate_gray"],
}
_KEYWORD_MOODS = [
    (("blood", "fire", "red", "ember", "meteor"), "crimson"),
    (("sunset", "golden", "gold", "solar", "sand", "treasure"), "gold"),
    (("aurora", "emerald", "chia", "green", "biolum", "kelp"), "green"),
    (("purple", "violet", "corrupt", "void", "wizard", "magic", "rune", "sigil"), "violet"),
    (("moon", "fog", "overcast", "frozen", "glass", "ghost", "lightning", "searchlight"), "pale"),
    (("black", "abyss", "midnight", "storm", "whirlpool", "grave", "skeleton"), "dark"),
]

BODY_COLORS = {
    "Green": ("chia_green", "teal_green"),
    "Blue": ("sea_blue", "steel_blue"),
    "Zombie": ("teal_green", "slate_gray"),
    "Ghost": ("pale_blue", "ash_gray"),
    "Gold": ("gold", "amber"),
    "Emerald": ("bright_green", "deep_teal"),
    "Corrupted": ("amethyst", "deep_violet"),
    "Chrome": ("ash_gray", "bone_white"),
}


def mood_for(name: str) -> str:
    low = name.lower()
    for keys, mood in _KEYWORD_MOODS:
        if any(k in low for k in keys):
            return mood
    return "blue"


class Det:
    """Deterministic parameter source from a sprite key."""

    def __init__(self, key: str):
        self._d = hashlib.sha256(key.encode()).digest()

    def byte(self, i: int) -> int:
        return self._d[i % 32]

    def frac(self, i: int, lo: float = 0.0, hi: float = 1.0) -> float:
        return lo + (self._d[i % 32] / 255.0) * (hi - lo)

    def pick(self, seq, i: int):
        return seq[self._d[i % 32] % len(seq)]


def col(name: str) -> tuple[int, int, int]:
    return _PALETTE[name]


# ------------------------------------------------------- drawing helpers

def vgrad(size: int, stops: list[tuple[float, tuple[int, int, int]]],
          y0: float = 0.0, y1: float = 1.0, alpha: int = 255) -> Image.Image:
    """Vertical gradient band between fractional rows y0..y1 (transparent
    elsewhere). Cheap row-fill; smooth enough at sprite scale."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    top, bot = int(y0 * size), int(y1 * size)
    span = max(1, bot - top)
    for row in range(top, bot):
        t = (row - top) / span
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                c = tuple(round(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
                d.line([(0, row), (size, row)], fill=(*c, alpha))
                break
    return img


def curve_points(p0, p1, p2, n=32):
    """Quadratic bezier sample points."""
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1])
            for t in (i / n for i in range(n + 1))]


def stroke(d: ImageDraw.ImageDraw, pts, color, width, alpha=255):
    d.line(pts, fill=(*color, alpha), width=width, joint="curve")


def blend(c1, c2, f=0.5):
    return tuple(round(c1[k] + (c2[k] - c1[k]) * f) for k in range(3))


def tag(d: ImageDraw.ImageDraw, size: int, slot: int, color):
    """Discreet 4-square placeholder checker tag; position varies per layer."""
    s = max(4, size // 96)
    x0 = (slot * 7 + 2) * s
    y0 = size - 3 * s
    for i in range(4):
        if i % 2 == 0:
            d.rectangle([x0 + i * s, y0, x0 + (i + 1) * s - 1, y0 + s - 1],
                        fill=(*color, 150))


# shared composition geometry (fractions of canvas)
HORIZON = 0.60
DECK_Y = 0.565
HEAD = (0.50, 0.415)
HEAD_R = 0.052


def _c(size, fx, fy):
    return (fx * size, fy * size)


# ----------------------------------------------------- layer renderers

def draw_sky(key, name, size) -> Image.Image:
    det = Det(key)
    mood = mood_for(name)
    a = col(det.pick(POOLS[mood], 0))
    b = col(det.pick(POOLS[mood], 1))
    deep = col(det.pick(POOLS["dark"], 2))
    img = vgrad(size, [(0.0, a), (0.55, blend(b, deep, 0.35)), (1.0, deep)])
    d = ImageDraw.Draw(img)
    if det.byte(3) % 3 == 0:  # a sun / moon / eclipse disc
        cx, cy = _c(size, det.frac(4, 0.6, 0.8), det.frac(5, 0.14, 0.30))
        r = size * det.frac(6, 0.05, 0.09)
        disc = blend(col("bone_white"), a, 0.35)
        for k in range(6, 0, -1):  # soft halo
            d.ellipse([cx - r - k * 3, cy - r - k * 3, cx + r + k * 3, cy + r + k * 3],
                      fill=(*disc, 10))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*disc, 210))
    if "meteor" in name.lower() or "lightning" in name.lower():
        for i in range(3):
            x = size * det.frac(8 + i, 0.1, 0.9)
            y = size * det.frac(11 + i, 0.05, 0.35)
            stroke(d, [(x, y), (x - size * 0.06, y + size * 0.12)],
                   col("pale_gold"), max(2, size // 300), 190)
    tag(d, size, 0, blend(a, deep))
    return img


def draw_sea(key, name, size) -> Image.Image:
    det = Det(key)
    mood = mood_for(name)
    tint = col(det.pick(POOLS[mood], 0))
    deep = col(det.pick(POOLS["dark"], 1))
    img = vgrad(size, [(0.0, blend(tint, deep, 0.45)), (1.0, col("ink_black"))],
                y0=HORIZON, y1=1.0)
    d = ImageDraw.Draw(img)
    amp = size * det.frac(2, 0.004, 0.014)
    for w in range(4):
        yb = size * (HORIZON + 0.05 + w * 0.09)
        pts = [(x, yb + amp * math.sin(x / size * math.tau * (2 + w) + det.frac(3 + w) * 6))
               for x in range(0, size + 8, 8)]
        stroke(d, pts, blend(tint, col("bone_white"), 0.25),
               max(2, size // 400), 90 - w * 18)
    if "whirlpool" in name.lower():
        cx, cy = _c(size, 0.5, 0.82)
        for t in range(120):
            ang = t / 120 * 3 * math.tau
            r = size * 0.16 * (1 - t / 130)
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang) * 0.4
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(*blend(tint, deep, 0.2), 120))
    tag(d, size, 1, blend(tint, deep))
    return img


def draw_scene(key, name, size, series) -> Image.Image:
    det = Det(key)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = col("deep_ink")
    accent = {"harbor": col("bronze"), "military": col("slate_gray"),
              "pirate": col("maroon"), "wizard": col("amethyst"),
              "crystal": col("pale_blue")}.get(series, col("slate_gray"))
    side = det.frac(0, 0.06, 0.16)
    if det.byte(9) % 2:
        side = 1 - side - 0.05
    # vertical structures on one flank
    for i in range(2 + det.byte(1) % 2):
        x = size * (side + i * 0.045)
        h = size * det.frac(2 + i, 0.10, 0.28)
        w = max(3, int(size * 0.012))
        d.rectangle([x, size * HORIZON - h, x + w, size * (HORIZON + 0.02)],
                    fill=(*ink, 200))
        d.ellipse([x - w, size * HORIZON - h - w * 2, x + 2 * w, size * HORIZON - h],
                  fill=(*accent, 170))
    if series in ("wizard", "crystal"):  # floating glyphs / shards
        for i in range(4):
            x = size * det.frac(6 + i, 0.1, 0.9)
            y = size * det.frac(10 + i, 0.20, 0.5)
            r = size * det.frac(14 + i, 0.008, 0.02)
            d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)],
                      fill=(*accent, 150))
    tag(d, size, 2, accent)
    return img


def draw_ship(key, name, size) -> Image.Image:
    det = Det(key)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = blend(col("deep_ink"), col("ink_black"), det.frac(0, 0.0, 0.6))
    if mood_for(name) == "crimson":
        ink = blend(ink, col("maroon"), 0.35)
    half_w = det.frac(1, 0.14, 0.30)
    hull_top = DECK_Y
    hull_bot = HORIZON + 0.03
    cx = 0.5
    # hull with swept bow/stern
    pts = [_c(size, cx - half_w, hull_top),
           _c(size, cx + half_w, hull_top),
           _c(size, cx + half_w * 0.82, hull_bot),
           _c(size, cx - half_w * 0.82, hull_bot)]
    d.polygon(pts, fill=(*ink, 235))
    bow = curve_points(_c(size, cx + half_w, hull_top),
                       _c(size, cx + half_w + 0.05 * size / size * size, hull_top * size - 0.05 * size)
                       if False else (size * (cx + half_w + 0.05), size * (hull_top - 0.05)),
                       (size * (cx + half_w + 0.015), size * (hull_top - 0.10)))
    stroke(d, bow, ink, max(3, size // 220), 235)
    masts = 1 + det.byte(2) % 3
    for m in range(masts):
        mx = cx - half_w * 0.55 + m * (half_w * 1.1 / max(1, masts - 1) if masts > 1 else 0)
        mh = det.frac(3 + m, 0.16, 0.30)
        x = size * mx
        d.line([(x, size * hull_top), (x, size * (hull_top - mh))],
               fill=(*ink, 235), width=max(3, size // 300))
        # swept sail: curved triangle
        sail_w = size * det.frac(6 + m, 0.05, 0.10)
        top = (x, size * (hull_top - mh))
        foot = (x + sail_w, size * (hull_top - mh * 0.25))
        mid = (x + sail_w * 0.9, size * (hull_top - mh * 0.72))
        d.polygon([top, mid, foot, (x, size * (hull_top - mh * 0.2))],
                  fill=(*blend(ink, col("bone_white"), 0.18), 210))
    # pennant
    fx, fy = size * (cx - half_w * 0.55), size * (hull_top - det.frac(3, 0.16, 0.30))
    d.polygon([(fx, fy), (fx - size * 0.03, fy + size * 0.012), (fx, fy + size * 0.024)],
              fill=(*col(det.pick(["crimson", "gold", "chia_green", "bone_white"], 9)), 220))
    tag(d, size, 3, ink)
    return img


def draw_condition(key, name, size) -> Image.Image:
    det = Det(key)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    low = name.lower()
    if "burn" in low or "fire" in low:
        cx, cy = _c(size, det.frac(0, 0.42, 0.58), DECK_Y - 0.02)
        for k in range(8, 0, -1):
            r = size * 0.02 * k
            d.ellipse([cx - r, cy - r * 1.4, cx + r, cy + r * 0.6],
                      fill=(*col("ember_orange"), 14))
        for i in range(5):
            x = cx + size * det.frac(2 + i, -0.06, 0.06)
            stroke(d, curve_points((x, cy), (x + size * 0.02, cy - size * 0.08),
                                   (x - size * 0.01, cy - size * 0.16)),
                   col("gold"), max(2, size // 400), 120)
    elif "flood" in low or "sunk" in low or "underwater" in low:
        depth = 0.10 if "half" in low else (0.16 if "flood" in low else 0.24)
        band = vgrad(size, [(0.0, col("sea_blue")), (1.0, col("deep_navy"))],
                     y0=HORIZON - depth, y1=HORIZON + 0.04, alpha=110)
        img.alpha_composite(band)
    elif "ghost" in low:
        veil = vgrad(size, [(0.0, col("pale_blue")), (1.0, col("ash_gray"))],
                     y0=0.30, y1=0.70, alpha=48)
        img.alpha_composite(veil)
    elif "rebuilt" in low or "salvage" in low:
        for i in range(6):
            x, y = _c(size, det.frac(i, 0.36, 0.64), det.frac(6 + i, 0.42, 0.56))
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(*col("gold"), 200))
        stroke(d, [_c(size, 0.34, DECK_Y - 0.10), _c(size, 0.66, DECK_Y - 0.13)],
               col("bronze"), max(2, size // 350), 190)
    elif "split" in low or "broken" in low:
        stroke(d, curve_points(_c(size, 0.5, DECK_Y), _c(size, 0.52, HORIZON),
                               _c(size, 0.47, HORIZON + 0.05)),
               col("ink_black"), max(3, size // 250), 220)
    elif "listing" in low:
        for i in range(4):
            y = size * (0.30 + i * 0.06)
            stroke(d, [(size * 0.15, y), (size * 0.35, y + size * 0.03)],
                   col("slate_gray"), max(2, size // 450), 70)
    tag(d, size, 4, col("slate_gray"))
    return img


def draw_body(key, variant, pose, size) -> Image.Image:
    det = Det(key)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c1, c2 = (col(a) for a in BODY_COLORS.get(variant, ("chia_green", "teal_green")))
    alpha = 150 if variant == "Ghost" else 235
    dx = {"On Bow": 0.07, "Back Turned": -0.02}.get(pose, 0.0)
    dy = {"Sitting": 0.035, "Looking Down": 0.012}.get(pose, 0.0)
    hx, hy = HEAD[0] + dx, HEAD[1] + dy
    r = HEAD_R
    # torso: teardrop that dissolves toward the deck (art-direction nod)
    torso = curve_points(_c(size, hx - r * 0.9, hy + r),
                         _c(size, hx - r * 1.7, hy + r * 4.2),
                         _c(size, hx, hy + r * 5.0)) + \
            curve_points(_c(size, hx, hy + r * 5.0),
                         _c(size, hx + r * 1.7, hy + r * 4.2),
                         _c(size, hx + r * 0.9, hy + r))
    d.polygon(torso, fill=(*blend(c1, c2, 0.45), alpha))
    # dissolving tendrils at the base
    for i in range(3):
        bx = hx + (i - 1) * r * 0.9
        stroke(d, curve_points(_c(size, bx, hy + r * 4.6),
                               _c(size, bx + det.frac(i, -0.02, 0.02), hy + r * 5.8),
                               _c(size, bx - det.frac(3 + i, -0.03, 0.03), hy + r * 6.6)),
               blend(c2, col("deep_navy"), 0.4), max(2, size // 350), alpha - 60)
    # head
    d.ellipse([size * (hx - r), size * (hy - r), size * (hx + r), size * (hy + r)],
              fill=(*c1, alpha))
    # tousled hair arc (black, Amano cue)
    hair = curve_points(_c(size, hx - r, hy - r * 0.2),
                        _c(size, hx - r * 0.2, hy - r * 1.9),
                        _c(size, hx + r * 1.05, hy - r * 0.45))
    stroke(d, hair, col("ink_black"), max(4, int(size * r * 0.55)), 245)
    if pose == "Saluting":
        stroke(d, [_c(size, hx + r * 1.1, hy + r * 2.2), _c(size, hx + r * 1.9, hy + r * 0.4)],
               blend(c1, c2, 0.45), max(3, size // 260), alpha)
    tag(d, size, 5, c2)
    return img


def draw_clothing(key, name, size) -> Image.Image:
    det = Det(key)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    mood = mood_for(name)
    base = col(det.pick(POOLS[mood], 0)) if mood != "blue" else \
        col(det.pick(["navy", "deep_navy", "steel_blue", "bronze", "maroon"], 0))
    hx, hy, r = HEAD[0], HEAD[1], HEAD_R
    torso = curve_points(_c(size, hx - r * 0.95, hy + r * 1.1),
                         _c(size, hx - r * 1.55, hy + r * 3.9),
                         _c(size, hx, hy + r * 4.5)) + \
            curve_points(_c(size, hx, hy + r * 4.5),
                         _c(size, hx + r * 1.55, hy + r * 3.9),
                         _c(size, hx + r * 0.95, hy + r * 1.1))
    d.polygon(torso, fill=(*base, 200))
    # gold filigree collar — the signature ornament
    collar = curve_points(_c(size, hx - r * 0.95, hy + r * 1.05),
                          _c(size, hx, hy + r * 1.55),
                          _c(size, hx + r * 0.95, hy + r * 1.05))
    stroke(d, collar, col("gold"), max(3, size // 260), 235)
    tag(d, size, 6, base)
    return img


def draw_eyes(key, name, size) -> Image.Image:
    det = Det(key)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    low = name.lower()
    color = col("bone_white")
    if "laser" in low or "heart" in low:
        color = col("crimson")
    elif "xch" in low or "wizard" in low:
        color = col("bright_green")
    elif "diamond" in low or "star" in low:
        color = col("pale_blue")
    elif "dead" in low or "closed" in low or "sleepy" in low:
        color = col("slate_gray")
    hx, hy, r = HEAD[0], HEAD[1], HEAD_R
    er = r * det.frac(0, 0.18, 0.26)
    for sgn in (-1, 1):
        x, y = size * (hx + sgn * r * 0.42), size * (hy - r * 0.05)
        if "closed" in low or "dead" in low:
            stroke(d, [(x - er * size / size * 8, y), (x + 8, y)], color,
                   max(2, size // 400), 220)
        else:
            d.ellipse([x - er * size, y - er * size, x + er * size, y + er * size],
                      fill=(*color, 235))
            d.ellipse([x - er * size * 0.3, y - er * size * 0.5,
                       x + er * size * 0.1, y - er * size * 0.1],
                      fill=(*col("ink_black"), 200))
    tag(d, size, 7, color)
    return img


def draw_mouth(key, name, size) -> Image.Image:
    det = Det(key)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hx, hy, r = HEAD[0], HEAD[1], HEAD_R
    mx, my = hx + r * 0.55, hy + r * 0.45
    low = name.lower()
    item = col(det.pick(["bronze", "sand", "maroon", "slate_gray"], 0))
    stroke(d, [_c(size, mx, my), _c(size, mx + r * 0.9, my - r * 0.15)],
           item, max(3, size // 300), 230)
    if any(k in low for k in ("cig", "pipe")):
        d.ellipse([size * (mx + r * 0.86) - 4, size * (my - r * 0.15) - 4,
                   size * (mx + r * 0.86) + 4, size * (my - r * 0.15) + 4],
                  fill=(*col("ember_orange"), 235))
        # ornate curling smoke — the Amano flourish
        sx, sy = mx + r * 0.95, my - r * 0.3
        for i in range(3):
            pts = curve_points(_c(size, sx, sy),
                               _c(size, sx + det.frac(2 + i, -0.10, 0.14),
                                  sy - 0.10 - i * 0.05),
                               _c(size, sx + det.frac(6 + i, -0.06, 0.10),
                                  sy - 0.20 - i * 0.07))
            stroke(d, pts, col("ash_gray"), max(2, size // 400), 110 - i * 25)
    tag(d, size, 8, item)
    return img


def draw_hat(key, name, size) -> Image.Image:
    det = Det(key)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hx, hy, r = HEAD[0], HEAD[1], HEAD_R
    low = name.lower()
    gold, ink = col("gold"), col("deep_ink")
    top = hy - r * 1.15
    if "halo" in low and "horn" not in low:
        d.ellipse([size * (hx - r * 0.8), size * (top - r * 0.9),
                   size * (hx + r * 0.8), size * (top - r * 0.3)],
                  outline=(*col("pale_gold"), 235), width=max(3, size // 250))
    elif "torn" in low:
        d.ellipse([size * (hx - r * 0.8), size * (top - r * 0.9),
                   size * (hx + r * 0.8), size * (top - r * 0.3)],
                  outline=(*col("pale_gold"), 235), width=max(3, size // 250))
        for sgn in (-1, 1):
            d.polygon([_c(size, hx + sgn * r * 0.75, top + r * 0.35),
                       _c(size, hx + sgn * r * 1.15, top - r * 0.45),
                       _c(size, hx + sgn * r * 0.45, top + r * 0.15)],
                      fill=(*col("maroon"), 235))
    elif "horn" in low:
        for sgn in (-1, 1):
            d.polygon([_c(size, hx + sgn * r * 0.75, top + r * 0.35),
                       _c(size, hx + sgn * r * 1.15, top - r * 0.45),
                       _c(size, hx + sgn * r * 0.45, top + r * 0.15)],
                      fill=(*col("maroon"), 235))
    elif "crown" in low:
        pts = []
        for i in range(5):
            x = hx - r * 0.7 + i * r * 0.35
            pts += [_c(size, x, top + (0 if i % 2 else r * 0.5))]
        d.polygon(pts + [_c(size, hx + r * 0.7, top + r * 0.7),
                         _c(size, hx - r * 0.7, top + r * 0.7)],
                  fill=(*gold, 235))
    elif "wizard" in low:
        d.polygon([_c(size, hx - r * 0.9, top + r * 0.6),
                   _c(size, hx + det.frac(0, 0.01, 0.05), top - r * 1.6),
                   _c(size, hx + r * 0.9, top + r * 0.6)],
                  fill=(*col("deep_violet"), 235))
        d.ellipse([size * (hx + r * 0.3) - 4, size * (top - r * 1.2) - 4,
                   size * (hx + r * 0.3) + 4, size * (top - r * 1.2) + 4],
                  fill=(*col("pale_gold"), 235))
    elif "diver" in low:
        d.ellipse([size * (hx - r * 1.15), size * (hy - r * 1.15),
                   size * (hx + r * 1.15), size * (hy + r * 1.15)],
                  outline=(*col("bronze"), 220), width=max(4, size // 180))
    else:  # generic band / cap family
        cap = col(det.pick(["navy", "maroon", "bronze", "slate_gray", "deep_teal"], 1))
        d.chord([size * (hx - r * 1.02), size * (top - r * 0.4),
                 size * (hx + r * 1.02), size * (top + r * 1.4)],
                180, 360, fill=(*cap, 235))
        if any(k in low for k in ("captain", "admiral", "pirate", "pilot")):
            stroke(d, [_c(size, hx - r * 1.05, top + r * 0.52),
                       _c(size, hx + r * 1.05, top + r * 0.52)],
                   gold, max(3, size // 300), 235)
    tag(d, size, 9, ink)
    return img


def draw_aura(key, name, size) -> Image.Image:
    det = Det(key)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    low = name.lower()
    color = col("bright_green")
    if "purple" in low or "corrupt" in low:
        color = col("amethyst")
    elif "crystal" in low:
        color = col("pale_blue")
    elif "halo" in low or "golden" in low:
        color = col("pale_gold")
    elif "laser" in low:
        color = col("crimson")
    elif "ghost" in low:
        color = col("ash_gray")
    elif "chia" in low:
        color = col("chia_green")
    cx, cy = HEAD[0], HEAD[1] + HEAD_R * 2.2
    # two interleaved swirl arcs around the character
    for k in range(2):
        pts = []
        for t in range(64):
            ang = t / 63 * math.tau * 0.8 + k * math.pi + det.frac(k, 0, 0.8)
            rad = (0.16 + 0.05 * math.sin(t / 9 + k)) * (1 + 0.15 * k)
            pts.append((size * (cx + rad * math.cos(ang)),
                        size * (cy + rad * 0.75 * math.sin(ang))))
        stroke(d, pts, color, max(3, size // 300), 90)
    if "static" in low:
        for i in range(14):
            x, y = _c(size, det.frac(i, 0.3, 0.7), det.frac(i + 14, 0.25, 0.65))
            d.rectangle([x, y, x + 4, y + 4], fill=(*color, 160))
    tag(d, size, 10, color)
    return img


# ------------------------------------------------- legacy pixel renderer

REGIONS = {
    "sky": (0, 0, 47, 47), "sea": (0, 30, 47, 47), "scene_element": (2, 14, 10, 34),
    "ship_class": (12, 22, 39, 34), "ship_condition": (12, 18, 39, 23),
    "body": (18, 10, 31, 33), "clothing": (18, 26, 31, 33), "eyes": (21, 14, 28, 17),
    "mouth": (22, 20, 27, 22), "hat": (17, 6, 32, 11), "aura": (1, 1, 46, 46),
}


def draw_pixel_placeholder(layer: str, key: str, master_colors) -> Image.Image:
    img = Image.new("RGBA", (PX_PIXEL, PX_PIXEL), (0, 0, 0, 0))
    px = img.load()
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    primary, accent = master_colors[h % 32], master_colors[(h // 32) % 32]
    x0, y0, x1, y1 = REGIONS[layer]
    if layer == "aura":
        for x in range(x0, x1 + 1):
            if x % 3 != 2:
                px[x, y0] = (*primary, 255)
                px[x, y1] = (*primary, 255)
        for y in range(y0, y1 + 1):
            if y % 3 != 2:
                px[x0, y] = (*primary, 255)
                px[x1, y] = (*primary, 255)
    else:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[x, y] = (*primary, 255)
        stripe_y = y0 + (int(hashlib.sha256((key + "/s").encode()).hexdigest(), 16)
                         % max(1, y1 - y0))
        for x in range(x0, x1 + 1):
            px[x, stripe_y] = (*accent, 255)
    for i in range(3):
        if (x0 + i) <= x1:
            px[x0 + i, y0] = (*(accent if i % 2 == 0 else primary), 255)
    return img


# ----------------------------------------------------------------- main

def render_illustration(layer_name: str, key: str, trait_name: str,
                        series: str | None, body_variant: str | None,
                        pose: str | None, out_px: int) -> Image.Image:
    size = out_px * SS
    if layer_name == "sky":
        img = draw_sky(key, trait_name, size)
    elif layer_name == "sea":
        img = draw_sea(key, trait_name, size)
    elif layer_name == "scene_element":
        img = draw_scene(key, trait_name, size, series)
    elif layer_name == "ship_class":
        img = draw_ship(key, trait_name, size)
    elif layer_name == "ship_condition":
        img = draw_condition(key, trait_name, size)
    elif layer_name == "body":
        img = draw_body(key, body_variant, pose, size)
    elif layer_name == "clothing":
        img = draw_clothing(key, trait_name, size)
    elif layer_name == "eyes":
        img = draw_eyes(key, trait_name, size)
    elif layer_name == "mouth":
        img = draw_mouth(key, trait_name, size)
    elif layer_name == "hat":
        img = draw_hat(key, trait_name, size)
    elif layer_name == "aura":
        img = draw_aura(key, trait_name, size)
    else:
        raise ValueError(f"no renderer for layer {layer_name}")
    return img.resize((out_px, out_px), Image.LANCZOS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("--profile", choices=["pixel", "illustration"], default=None,
                    help="target render profile (default: config/render.json active_profile)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = GenConfig()
    render_doc = load_json(CONFIG_DIR / "render.json")
    profile_name = args.profile or render_doc["active_profile"]
    out_px = int(render_doc["profiles"][profile_name]["master_px"])
    master_colors = list(_PALETTE.values())

    written = skipped = 0
    for layer in cfg.layers:
        if layer.rendered_via:
            continue
        ldir = SPRITES / layer.name
        ldir.mkdir(parents=True, exist_ok=True)
        jobs: list[tuple[str, str, str | None, str | None, str | None]] = []
        # (filename, trait/desc, series, body_variant, pose)
        if layer.sprite_pattern:
            pose_layer = cfg.layer_by_name["pose"]
            for t in layer.traits:
                for p in pose_layer.traits:
                    rel = layer.sprite_pattern.format(body=_snake(t.name), pose=_snake(p.name))
                    jobs.append((Path(rel).name, f"{t.name} x {p.name}", None, t.name, p.name))
        else:
            for t in layer.traits:
                if t.sprite_filename:
                    jobs.append((t.sprite_filename, t.name, t.series, None, None))

        for fname, desc, series, variant, pose in jobs:
            path = ldir / fname
            if path.exists() and not args.force:
                skipped += 1
                continue
            key = f"{layer.name}/{fname}"
            trait_name = desc.split(" x ")[0]
            if profile_name == "pixel":
                img = draw_pixel_placeholder(layer.name, key, master_colors)
                if out_px != PX_PIXEL:
                    img = img.resize((out_px, out_px), Image.NEAREST)
            else:
                img = render_illustration(layer.name, key, trait_name, series,
                                          variant, pose, out_px)
            img.save(path)
            written += 1

        lines = [
            f"# sprites/{layer.name} — {layer.display_name}",
            "",
            f"z-order: {layer.z_order} | required: {layer.required} | "
            f"dimensions: {out_px}x{out_px} RGBA PNG ({profile_name} profile)",
            "",
            "> **PLACEHOLDERS**: every PNG here is generated stand-in art (gradient/",
            "> silhouette style sketch with a small corner checker tag). Replace with",
            "> final Amano illustration per docs/art-reference/ART-DIRECTION.md,",
            "> file-for-file; filenames must not change.",
            "",
            "| file | trait |",
            "|---|---|",
        ]
        lines += [f"| `{f}` | {dsc} |" for f, dsc, *_ in jobs]
        (ldir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    log.info("placeholders (%s profile, %dpx): %d written, %d kept",
             profile_name, out_px, written, skipped)
    return 0


def _snake(name: str) -> str:
    import re
    s = name.lower().replace("'", "").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r" +", "_", s.strip())


if __name__ == "__main__":
    sys.exit(main())
