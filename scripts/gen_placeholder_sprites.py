# SPDX-License-Identifier: MIT
"""Generate PLACEHOLDER sprites + per-layer READMEs from traits.json (P4).

Two renderers, chosen by render profile (config/render.json):

  pixel        — the original 48x48 solid-block placeholders (kept verbatim).
  illustration — Amano ink stand-ins matching ships_amano/ + ART-DIRECTION:
                 bone-white ground, vertical gradient linework (warm->navy),

                 calligraphic hulls, crystals, wave ribbons, gestural figures.
                 Deterministic per trait (sha256 of the sprite key).
                 Measured by scripts/style_score.py against ships_amano.

They remain placeholders (corner checker tag + README disclaimer) — replace
file-for-file with final illustration; filenames must not change.

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

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from shipgen.amano_ink import (  # noqa: E402
    DECK_Y,
    HEAD,
    HEAD_R,
    HORIZON,
    InkCanvas,
    RAMPS,
    chain_links,
    character_profile,
    crystal,
    filigree_curl,
    gun_turret,
    mast_and_sail,
    mood_ramp,
    network_mesh,
    organic_hull,
    placeholder_tag,
    qbez,
    smoke_flourish,
    soft_atmosphere,
    wave_ribbons,
    catmull,
)
from shipgen.config import GenConfig, load_json, CONFIG_DIR  # noqa: E402

log = logging.getLogger("gen_placeholder_sprites")
ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "sprites"

PX_PIXEL = 48
# Draw at this working size then LANCZOS up to master_px (speed + AA).
WORK_PX = 1024

# ---------------------------------------------------------------- palette

_PALETTE = {
    c["name"]: tuple(int(c["hex"][i : i + 2], 16) for i in (1, 3, 5))
    for c in load_json(CONFIG_DIR / "palette.json")["master"]
}

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
    (("blood", "fire", "red", "ember", "meteor", "burn"), "crimson"),
    (("sunset", "golden", "gold", "solar", "sand", "treasure"), "gold"),
    (("aurora", "emerald", "chia", "green", "biolum", "kelp"), "green"),
    (("purple", "violet", "corrupt", "void", "wizard", "magic", "rune", "sigil"), "violet"),
    (("moon", "fog", "overcast", "frozen", "glass", "ghost", "lightning", "searchlight"), "pale"),
    (("black", "abyss", "midnight", "storm", "whirlpool", "grave", "skeleton"), "dark"),
]

BODY_COLORS = {
    "Green": "green",
    "Blue": "blue",
    "Zombie": "green",
    "Ghost": "pale",
    "Gold": "gold",
    "Emerald": "green",
    "Corrupted": "violet",
    "Chrome": "pale",
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


# ----------------------------------------------------- layer renderers

def draw_sky(key: str, name: str, size: int) -> Image.Image:
    """Near-white atmosphere — wisps only, never a solid colour block."""
    det = Det(key)
    mood = mood_for(name)
    stops = mood_ramp(mood)
    ink = InkCanvas(size, y0=0.05, y1=0.55)
    soft_atmosphere(ink, stops, density=5 + det.byte(0) % 4, alpha=22 + det.byte(1) % 16)
    # optional celestial disc as thin gradient ring
    if det.byte(2) % 3 == 0:
        cx = size * det.frac(3, 0.62, 0.82)
        cy = size * det.frac(4, 0.12, 0.28)
        r = size * det.frac(5, 0.04, 0.08)
        for k in range(3):
            ink.ellipse(
                [cx - r - k * 2, cy - r - k * 2, cx + r + k * 2, cy + r + k * 2],
                stops, alpha=0, outline_w=max(1, size // 400),
            )
        # faint fill
        ink.ellipse([cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7], stops, 35)
    if "meteor" in name.lower() or "lightning" in name.lower():
        for i in range(3):
            x = size * det.frac(8 + i, 0.15, 0.85)
            y = size * det.frac(11 + i, 0.08, 0.32)
            ink.stroke(
                [(x, y), (x - size * 0.05, y + size * 0.14)],
                stops, max(1.5, size * 0.002), 180,
            )
    if "aurora" in name.lower():
        for i in range(4):
            pts = catmull([
                (size * 0.1, size * (0.15 + i * 0.04)),
                (size * 0.35, size * (0.10 + i * 0.05)),
                (size * 0.65, size * (0.18 + i * 0.03)),
                (size * 0.9, size * (0.12 + i * 0.04)),
            ], 6)
            ink.stroke(pts, mood_ramp("green"), max(1.5, size * 0.002), 90)
    placeholder_tag(ink, 0)
    return ink.img


def draw_sea(key: str, name: str, size: int) -> Image.Image:
    """Flowing wave ribbons on transparent ground — ships_amano / Hokusai water."""
    det = Det(key)
    mood = mood_for(name)
    stops = mood_ramp(mood if mood != "pale" else "blue")
    ink = InkCanvas(size, y0=HORIZON - 0.05, y1=0.95)
    strands = 10 + det.byte(0) % 5
    wave_ribbons(
        ink, y_base=HORIZON + 0.01, amp=0.04 + det.frac(1, 0, 0.02),
        length=1.0, stops=stops, strands=strands,
        width=max(2.2, size * 0.0035), phase=det.frac(2, 0, 3),
    )
    # secondary lower swell denser (cooler end of ramp)
    wave_ribbons(
        ink, y_base=0.76, amp=0.045, length=1.0, stops=stops,
        strands=8, width=max(1.8, size * 0.0028), phase=det.frac(3, 1, 4),
        x0=0.0, x1=1.0,
    )
    if "whirlpool" in name.lower():
        cx, cy = 0.5 * size, 0.82 * size
        px, py = None, None
        for t in range(90):
            ang = t / 90 * 2.8 * math.tau
            rad = size * 0.18 * (1 - t / 100)
            x = cx + rad * math.cos(ang)
            y = cy + rad * math.sin(ang) * 0.45
            if px is not None:
                ink.stroke([(px, py), (x, y)], stops, max(1.2, size * 0.002), 160)
            px, py = x, y
    if "storm" in name.lower() or "swell" in name.lower():
        # breaking crest flourish
        crest = catmull([
            (size * 0.55, size * 0.62),
            (size * 0.72, size * 0.48),
            (size * 0.88, size * 0.40),
            (size * 0.78, size * 0.55),
            (size * 0.70, size * 0.68),
        ], 8)
        ink.stroke(crest, stops, max(2.0, size * 0.0035), 200)
        for i in range(8):
            filigree_curl(
                ink, size * (0.7 + det.frac(4 + i, -0.08, 0.08)),
                size * (0.45 + i * 0.02), size * 0.03, stops,
                turns=1.1, width=max(1.0, size * 0.0015), phase=i,
            )
    placeholder_tag(ink, 1)
    return ink.img


def draw_scene(key: str, name: str, size: int, series: str | None) -> Image.Image:
    det = Det(key)
    mood = {
        "harbor": "gold", "military": "blue", "pirate": "crimson",
        "wizard": "violet", "crystal": "blue",
    }.get(series or "", mood_for(name))
    stops = mood_ramp(mood)
    ink = InkCanvas(size, y0=0.2, y1=HORIZON + 0.05)
    side = det.frac(0, 0.06, 0.14)
    if det.byte(1) % 2:
        side = 1.0 - side - 0.08
    # pier / ruin posts as thin calligraphic uprights
    for i in range(2 + det.byte(2) % 2):
        x = (side + i * 0.04) * size
        h = size * det.frac(3 + i, 0.12, 0.28)
        ink.stroke([(x, HORIZON * size), (x, HORIZON * size - h)], stops,
                   max(1.5, size * 0.0025), 200)
        filigree_curl(ink, x, HORIZON * size - h, size * 0.025, stops, width=1.5)
    if series in ("wizard", "crystal") or "crystal" in (name or "").lower():
        for i in range(3):
            crystal(
                ink,
                size * det.frac(8 + i, 0.15, 0.85),
                size * det.frac(12 + i, 0.28, 0.48),
                size * det.frac(16 + i, 0.04, 0.09),
                size * det.frac(20 + i, 0.015, 0.035),
                stops, tilt=det.frac(24 + i, -0.3, 0.3),
            )
    if series == "pirate":
        # crescent moon filigree
        cx, cy = size * 0.78, size * 0.22
        for a in range(20):
            t0, t1 = a / 20 * math.pi, (a + 1) / 20 * math.pi
            ink.stroke([
                (cx + size * 0.08 * math.cos(t0), cy + size * 0.08 * math.sin(t0)),
                (cx + size * 0.08 * math.cos(t1), cy + size * 0.08 * math.sin(t1)),
            ], stops, max(1.5, size * 0.002), 180)
    placeholder_tag(ink, 2)
    return ink.img


def _ship_crystals(ink: InkCanvas, cx: float, top_y: float, stops, det: Det, n: int = 4) -> None:
    for i in range(n):
        crystal(
            ink,
            (cx + det.frac(10 + i, -0.08, 0.08)) * ink.size,
            top_y * ink.size - i * ink.size * 0.02,
            ink.size * det.frac(14 + i, 0.05, 0.12),
            ink.size * det.frac(18 + i, 0.018, 0.04),
            stops,
            tilt=det.frac(22 + i, -0.35, 0.35),
            fill_alpha=160 + det.byte(i) % 50,
        )


def draw_ship(key: str, name: str, size: int) -> Image.Image:
    """Ornate gradient-ink vessel — primary ships_amano grammar target."""
    det = Det(key)
    low = name.lower()
    mood = mood_for(name)
    if "ghost" in low:
        mood = "pale"
    elif "wizard" in low:
        mood = "violet"
    elif "blockchain" in low:
        mood = "violet" if det.byte(0) % 2 else "crimson"
    elif "pirate" in low:
        mood = "crimson"
    stops = mood_ramp(mood)
    # capital-ship ramps locked to ships_amano exemplars
    if "battleship" in low:
        stops = RAMPS["coral_navy"]
    elif "blockchain" in low:
        stops = RAMPS["crimson_navy"] if det.byte(1) % 2 else RAMPS["green_navy"]
    elif "aircraft" in low or "carrier" in low:
        stops = RAMPS["crimson_navy"]

    ink = InkCanvas(size, y0=0.18, y1=0.78)
    cx = 0.50
    deck = DECK_Y
    half_w = {
        "raft": 0.12, "lifeboat": 0.13, "fishing": 0.16, "tug": 0.15,
        "cargo": 0.22, "steam": 0.20, "yacht": 0.18, "cruiser": 0.24,
        "battleship": 0.28, "aircraft": 0.32, "submarine": 0.22,
        "pirate": 0.22, "ghost": 0.20, "ark": 0.26, "wizard": 0.20,
        "blockchain": 0.24,
    }
    hw = 0.20
    for k, v in half_w.items():
        if k in low:
            hw = v
            break
    depth = 0.10 if "raft" in low or "lifeboat" in low else 0.14

    organic_hull(ink, cx, deck, hw, depth, stops,
                 bow_lift=0.05 + det.frac(2, 0, 0.04),
                 fill_alpha=10 if "ghost" not in low else 6)

    # class-specific superstructure
    if "battleship" in low or "cruiser" in low:
        for i, gx in enumerate((cx - hw * 0.45, cx - hw * 0.05, cx + hw * 0.35)):
            gun_turret(ink, gx, deck - 0.03 - i * 0.01, 0.022 + i * 0.004, stops,
                       angle=-0.25 + i * 0.05)
        # tower
        ink.stroke(
            [(cx * size, deck * size), (cx * size, (deck - 0.18) * size)],
            stops, max(2.0, size * 0.003), 220,
        )
        for ty in (0.06, 0.10, 0.14):
            ink.stroke(
                [((cx - 0.04) * size, (deck - ty) * size),
                 ((cx + 0.05) * size, (deck - ty) * size)],
                stops, max(1.2, size * 0.002), 180,
            )
        _ship_crystals(ink, cx, deck - 0.20, stops, det, n=5)
        # organic armor swirls — density toward ships_amano plating
        for i in range(14):
            filigree_curl(
                ink, (cx + det.frac(5 + i, -hw, hw) * 0.85) * size,
                (deck + 0.01 + (i % 7) * 0.018) * size, size * (0.028 + (i % 3) * 0.008),
                stops, turns=1.3 + (i % 3) * 0.2,
                width=max(1.2, size * 0.0018), phase=i * 0.55, n=36,
            )

    elif "aircraft" in low or "carrier" in low:
        # flat deck line
        ink.stroke(
            [((cx - hw) * size, deck * size), ((cx + hw) * size, (deck - 0.02) * size)],
            stops, max(2.5, size * 0.004), 230,
        )
        # island superstructure
        ix = (cx + hw * 0.55) * size
        for h in (0.08, 0.14, 0.20):
            ink.stroke([(ix, deck * size), (ix, (deck - h) * size)], stops,
                       max(2.0, size * 0.003), 210)
        ink.stroke(
            [(ix - size * 0.04, (deck - 0.14) * size),
             (ix + size * 0.05, (deck - 0.14) * size)],
            stops, max(1.5, size * 0.002), 190,
        )
        # jets as chevrons
        for i in range(5):
            jx = (cx - hw * 0.6 + i * 0.08) * size
            jy = (deck - 0.04 - det.frac(8 + i, 0, 0.03)) * size
            ink.stroke(
                [(jx, jy), (jx + size * 0.035, jy - size * 0.008),
                 (jx, jy - size * 0.004)],
                stops, max(1.2, size * 0.002), 170,
            )
        _ship_crystals(ink, cx - 0.05, deck - 0.08, stops, det, n=4)

    elif "blockchain" in low:
        # mesh sail
        nodes = []
        for i in range(5):
            for j in range(4):
                nodes.append((
                    cx - 0.08 + i * 0.05 + det.frac(i * 4 + j, -0.01, 0.01),
                    deck - 0.28 + j * 0.06 + det.frac(20 + i + j, -0.01, 0.01),
                ))
        network_mesh(ink, nodes, stops, width=max(1.2, size * 0.0018))
        # mast poles
        for mx in (cx - 0.08, cx + 0.12):
            ink.stroke(
                [(mx * size, deck * size), (mx * size, (deck - 0.32) * size)],
                stops, max(1.5, size * 0.0025), 200,
            )
        chain_links(ink, (cx - 0.15, deck + 0.02), (cx + 0.18, deck + 0.08), 8, stops)
        # cubes
        for i in range(4):
            bx = (cx + det.frac(30 + i, -0.15, 0.15)) * size
            by = (deck + 0.06 + det.frac(34 + i, 0, 0.06)) * size
            s = size * 0.02
            ink.stroke(
                [(bx, by), (bx + s, by - s * 0.3), (bx + s, by + s * 0.7),
                 (bx, by + s), (bx, by)],
                stops, max(1.2, size * 0.0018), 190,
            )
        _ship_crystals(ink, cx - 0.05, deck - 0.22, stops, det, n=5)
        smoke_flourish(ink, (cx - 0.2, deck - 0.05), stops, strands=3, height=0.2)

    elif "pirate" in low or "ghost" in low:
        masts = 3 if "pirate" in low else 2
        for m in range(masts):
            mx = cx - hw * 0.55 + m * (hw * 1.0 / max(1, masts - 1))
            mh = 0.22 + det.frac(4 + m, 0, 0.08)
            mast_and_sail(ink, mx, deck, mh, 0.08 + det.frac(8 + m, 0, 0.04),
                          stops, billow=0.7 + det.frac(12 + m, 0, 0.3))
        # crescent / filigree moon for pirate
        if "pirate" in low:
            filigree_curl(ink, size * 0.78, size * 0.22, size * 0.09, stops,
                          turns=1.6, width=max(1.5, size * 0.0025))
        if "ghost" in low:
            smoke_flourish(ink, (cx, deck - 0.15), stops, strands=5, height=0.25)
        _ship_crystals(ink, cx, deck - 0.18, stops, det, n=2)

    elif "submarine" in low:
        # elongated body already hull; conning tower
        ink.stroke(
            [(cx * size, deck * size), (cx * size, (deck - 0.08) * size)],
            stops, max(2.5, size * 0.004), 220,
        )
        ink.ellipse(
            [(cx - 0.03) * size, (deck - 0.10) * size,
             (cx + 0.03) * size, (deck - 0.04) * size],
            stops, 50,
        )
        for i in range(4):
            fx = (cx - hw * 0.5 + i * 0.08) * size
            ink.ellipse([fx - 4, deck * size + 8, fx + 4, deck * size + 16], stops, 100)

    elif "wizard" in low or "ark" in low:
        for m in range(2):
            mx = cx - 0.08 + m * 0.14
            mast_and_sail(ink, mx, deck, 0.26, 0.10, stops, billow=0.9)
        for i in range(6):
            filigree_curl(
                ink, size * det.frac(10 + i, 0.3, 0.7),
                size * det.frac(16 + i, 0.25, 0.45), size * 0.04, stops,
                turns=1.5, width=1.5, phase=i,
            )
        _ship_crystals(ink, cx, deck - 0.22, stops, det, n=4)

    else:
        # generic small craft: 1–2 masts or cabin
        if any(k in low for k in ("yacht", "steam", "cargo", "fishing", "tug")):
            ink.stroke(
                [((cx - 0.04) * size, deck * size),
                 ((cx - 0.04) * size, (deck - 0.10) * size)],
                stops, max(2.0, size * 0.003), 210,
            )
            ink.stroke(
                [((cx - 0.08) * size, (deck - 0.06) * size),
                 ((cx + 0.06) * size, (deck - 0.06) * size)],
                stops, max(1.5, size * 0.002), 180,
            )
            if "steam" in low:
                smoke_flourish(ink, (cx - 0.04, deck - 0.10), stops, strands=3, height=0.18)
            if "yacht" in low or "cargo" in low:
                mast_and_sail(ink, cx + 0.06, deck, 0.16, 0.07, stops)
        else:
            mast_and_sail(ink, cx, deck, 0.12, 0.06, stops)

    # waterline flourish under hull
    wave_ribbons(
        ink, y_base=deck + depth - 0.01, amp=0.02, length=1.0, stops=stops,
        strands=3, width=max(1.5, size * 0.002), phase=det.frac(0, 0, 2),
        x0=cx - hw - 0.05, x1=cx + hw + 0.08,
    )
    placeholder_tag(ink, 3)
    return ink.img


def draw_condition(key: str, name: str, size: int) -> Image.Image:
    det = Det(key)
    low = name.lower()
    ink = InkCanvas(size, y0=0.25, y1=0.75)
    if "burn" in low or "fire" in low:
        stops = mood_ramp("crimson")
        for i in range(6):
            smoke_flourish(
                ink,
                (0.42 + det.frac(i, -0.08, 0.12), DECK_Y - 0.02),
                stops, strands=2, height=0.12 + det.frac(6 + i, 0, 0.08),
                phase=i,
            )
        for i in range(4):
            crystal(
                ink, size * (0.45 + i * 0.04), size * (DECK_Y - 0.05),
                size * 0.03, size * 0.012, stops, fill_alpha=100,
            )
    elif "flood" in low or "sunk" in low or "underwater" in low:
        stops = mood_ramp("blue")
        depth = 0.08 if "half" in low else (0.12 if "flood" in low else 0.18)
        wave_ribbons(
            ink, y_base=HORIZON - depth, amp=0.025, length=1.0, stops=stops,
            strands=6, width=max(1.5, size * 0.0025),
        )
    elif "ghost" in low:
        stops = mood_ramp("pale")
        smoke_flourish(ink, (0.5, DECK_Y - 0.1), stops, strands=6, height=0.3)
    elif "rebuilt" in low or "salvage" in low:
        stops = mood_ramp("gold")
        for i in range(5):
            x = size * (0.38 + i * 0.05)
            y = size * (DECK_Y - 0.04)
            ink.stroke([(x, y), (x + 8, y - 12), (x - 4, y - 10), (x, y)],
                       stops, 1.5, 200)
        ink.stroke(
            [(size * 0.35, size * (DECK_Y - 0.08)),
             (size * 0.65, size * (DECK_Y - 0.12))],
            stops, max(2.0, size * 0.003), 200,
        )
    elif "split" in low or "broken" in low:
        stops = mood_ramp("dark")
        ink.stroke(
            qbez(
                (size * 0.5, size * DECK_Y),
                (size * 0.55, size * HORIZON),
                (size * 0.42, size * (HORIZON + 0.06)),
                20,
            ),
            stops, max(2.5, size * 0.004), 220,
        )
    elif "listing" in low:
        stops = mood_ramp("blue")
        for i in range(5):
            y = size * (0.32 + i * 0.05)
            ink.stroke(
                [(size * 0.12, y), (size * 0.32, y + size * 0.025)],
                stops, max(1.2, size * 0.002), 100,
            )
    else:
        stops = mood_ramp("blue")
        soft_atmosphere(ink, stops, density=3, alpha=20)
    placeholder_tag(ink, 4)
    return ink.img


def draw_body(key: str, variant: str, pose: str, size: int) -> Image.Image:
    mood = BODY_COLORS.get(variant, "green")
    stops = mood_ramp(mood)
    ink = InkCanvas(size, y0=0.25, y1=0.75)
    dx = {"On Bow": 0.06, "Back Turned": -0.03}.get(pose, 0.0)
    dy = {"Sitting": 0.04, "Looking Down": 0.015}.get(pose, 0.0)
    facing = -1.0 if pose == "Back Turned" else 1.0
    character_profile(
        ink, HEAD[0] + dx, HEAD[1] + dy, HEAD_R * (1.05 if variant != "Ghost" else 1.0),
        stops, facing=facing, hair=True, dissolve=True,
        fill_alpha=30 if variant == "Ghost" else 55,
    )
    if pose == "Saluting":
        hx, hy, r = (HEAD[0] + dx) * size, (HEAD[1] + dy) * size, HEAD_R * size
        ink.stroke(
            qbez(
                (hx + facing * r * 1.2, hy + r * 2.0),
                (hx + facing * r * 2.0, hy + r * 0.8),
                (hx + facing * r * 1.6, hy - r * 0.2),
                16,
            ),
            stops, max(2.0, size * 0.003), 210,
        )
    placeholder_tag(ink, 5)
    return ink.img


def draw_clothing(key: str, name: str, size: int) -> Image.Image:
    mood = mood_for(name)
    stops = mood_ramp(mood if mood != "blue" else "ink")
    ink = InkCanvas(size, y0=0.35, y1=0.72)
    hx, hy, r = HEAD[0] * size, HEAD[1] * size, HEAD_R * size
    # open jacket folds — line only
    left = qbez(
        (hx - r * 0.9, hy + r * 1.1),
        (hx - r * 1.6, hy + r * 2.8),
        (hx - r * 0.4, hy + r * 4.5),
        20,
    )
    right = qbez(
        (hx + r * 0.9, hy + r * 1.1),
        (hx + r * 1.5, hy + r * 2.8),
        (hx + r * 0.3, hy + r * 4.5),
        20,
    )
    ink.stroke(left, stops, max(2.0, size * 0.003), 210)
    ink.stroke(right, stops, max(2.0, size * 0.003), 210)
    # collar folds
    for i in range(3):
        ink.stroke(
            qbez(
                (hx - r * 0.7, hy + r * (1.2 + i * 0.15)),
                (hx, hy + r * (1.5 + i * 0.2)),
                (hx + r * 0.7, hy + r * (1.2 + i * 0.15)),
                12,
            ),
            stops, max(1.2, size * 0.002), 160,
        )
    # gold filigree collar — signature ornament
    gold = mood_ramp("gold")
    collar = qbez(
        (hx - r * 1.0, hy + r * 1.05),
        (hx, hy + r * 1.65),
        (hx + r * 1.0, hy + r * 1.05),
        20,
    )
    ink.stroke(collar, gold, max(2.5, size * 0.0035), 230)
    for i in range(4):
        filigree_curl(
            ink, hx + (i - 1.5) * r * 0.45, hy + r * 1.35, r * 0.2, gold,
            turns=1.0, width=max(1.0, size * 0.0015), phase=i,
        )
    placeholder_tag(ink, 6)
    return ink.img


def draw_eyes(key: str, name: str, size: int) -> Image.Image:
    det = Det(key)
    low = name.lower()
    if "laser" in low or "heart" in low:
        stops = mood_ramp("crimson")
    elif "xch" in low or "wizard" in low:
        stops = mood_ramp("green")
    elif "diamond" in low or "star" in low:
        stops = mood_ramp("blue")
    else:
        stops = mood_ramp("pale")
    ink = InkCanvas(size, y0=0.30, y1=0.45)
    hx, hy, r = HEAD[0] * size, HEAD[1] * size, HEAD_R * size
    er = r * det.frac(0, 0.22, 0.32)
    for sgn in (-1, 1):
        x, y = hx + sgn * r * 0.42, hy - r * 0.05
        if "closed" in low or "dead" in low:
            ink.stroke([(x - er, y), (x + er, y)], stops, max(1.5, size * 0.0025), 220)
        else:
            ink.ellipse([x - er, y - er * 0.85, x + er, y + er * 0.85], stops, 50)
            ink.ellipse([x - er, y - er * 0.85, x + er, y + er * 0.85], stops, 0,
                        outline_w=max(1, size // 400))
            ink.ellipse(
                [x - er * 0.25, y - er * 0.3, x + er * 0.15, y + er * 0.05],
                [(13, 13, 22)] * 3, 230,
            )
    placeholder_tag(ink, 7)
    return ink.img


def draw_mouth(key: str, name: str, size: int) -> Image.Image:
    det = Det(key)
    low = name.lower()
    stops = mood_ramp(mood_for(name))
    ink = InkCanvas(size, y0=0.35, y1=0.70)
    hx, hy, r = HEAD[0] * size, HEAD[1] * size, HEAD_R * size
    mx, my = hx + r * 0.55, hy + r * 0.45
    ink.stroke([(mx, my), (mx + r * 0.95, my - r * 0.12)], stops,
               max(2.0, size * 0.003), 230)
    if any(k in low for k in ("cig", "pipe", "cigarette")):
        ink.ellipse(
            [mx + r * 0.85 - 3, my - r * 0.15 - 3, mx + r * 0.85 + 3, my - r * 0.15 + 3],
            mood_ramp("crimson"), 230,
        )
        smoke_flourish(
            ink, ((mx + r * 0.9) / size, (my - r * 0.35) / size),
            mood_ramp("crimson"), strands=4, height=0.22, phase=det.frac(0, 0, 2),
        )
    placeholder_tag(ink, 8)
    return ink.img


def draw_hat(key: str, name: str, size: int) -> Image.Image:
    low = name.lower()
    stops = mood_ramp(mood_for(name))
    gold = mood_ramp("gold")
    ink = InkCanvas(size, y0=0.22, y1=0.45)
    hx, hy, r = HEAD[0] * size, HEAD[1] * size, HEAD_R * size
    top = hy - r * 1.15
    if "halo" in low:
        ink.ellipse(
            [hx - r * 0.85, top - r * 0.95, hx + r * 0.85, top - r * 0.25],
            gold, 0, outline_w=max(2, size // 280),
        )
        if "torn" in low or "horn" in low:
            for sgn in (-1, 1):
                ink.stroke(
                    qbez(
                        (hx + sgn * r * 0.7, top + r * 0.2),
                        (hx + sgn * r * 1.2, top - r * 0.5),
                        (hx + sgn * r * 0.5, top - r * 0.9),
                        12,
                    ),
                    mood_ramp("crimson"), max(2.0, size * 0.003), 230,
                )
    elif "horn" in low:
        for sgn in (-1, 1):
            ink.stroke(
                qbez(
                    (hx + sgn * r * 0.7, top + r * 0.2),
                    (hx + sgn * r * 1.2, top - r * 0.5),
                    (hx + sgn * r * 0.5, top - r * 0.9),
                    12,
                ),
                mood_ramp("crimson"), max(2.0, size * 0.003), 230,
            )
    elif "crown" in low:
        pts = []
        for i in range(5):
            x = hx - r * 0.7 + i * r * 0.35
            y = top + (0 if i % 2 else r * 0.45)
            pts.append((x, y))
        pts += [(hx + r * 0.7, top + r * 0.7), (hx - r * 0.7, top + r * 0.7)]
        ink.stroke(pts + [pts[0]], gold, max(2.0, size * 0.003), 230)
    elif "wizard" in low:
        ink.stroke(
            [(hx - r * 0.9, top + r * 0.55), (hx + r * 0.05, top - r * 1.55),
             (hx + r * 0.9, top + r * 0.55)],
            mood_ramp("violet"), max(2.0, size * 0.003), 230,
        )
        filigree_curl(ink, hx + r * 0.2, top - r * 0.8, r * 0.25, gold, turns=1.2)
    elif "diver" in low:
        ink.ellipse(
            [hx - r * 1.2, hy - r * 1.2, hx + r * 1.2, hy + r * 1.2],
            mood_ramp("gold"), 0, outline_w=max(3, size // 200),
        )
    else:
        # band / cap outline
        ink.stroke(
            catmull([
                (hx - r * 1.05, top + r * 0.55),
                (hx - r * 0.6, top - r * 0.15),
                (hx + r * 0.6, top - r * 0.15),
                (hx + r * 1.05, top + r * 0.55),
            ], 6),
            stops, max(2.0, size * 0.003), 220,
        )
        if any(k in low for k in ("captain", "admiral", "pirate", "pilot")):
            ink.stroke(
                [(hx - r * 1.1, top + r * 0.55), (hx + r * 1.1, top + r * 0.55)],
                gold, max(2.0, size * 0.003), 230,
            )
    placeholder_tag(ink, 9)
    return ink.img


def draw_aura(key: str, name: str, size: int) -> Image.Image:
    det = Det(key)
    low = name.lower()
    if "purple" in low or "corrupt" in low:
        mood = "violet"
    elif "crystal" in low:
        mood = "blue"
    elif "halo" in low or "golden" in low:
        mood = "gold"
    elif "laser" in low:
        mood = "crimson"
    elif "ghost" in low:
        mood = "pale"
    elif "chia" in low or "green" in low:
        mood = "green"
    else:
        mood = "green"
    stops = mood_ramp(mood)
    ink = InkCanvas(size, y0=0.2, y1=0.75)
    cx, cy = HEAD[0], HEAD[1] + HEAD_R * 2.0
    for k in range(3):
        pts = []
        for t in range(56):
            ang = t / 55 * math.tau * 0.85 + k * 2.0 + det.frac(k, 0, 1)
            rad = (0.14 + 0.05 * math.sin(t / 8 + k)) * (1 + 0.12 * k)
            pts.append((
                size * (cx + rad * math.cos(ang)),
                size * (cy + rad * 0.72 * math.sin(ang)),
            ))
        ink.stroke(pts, stops, max(1.5, size * 0.0025), 100 - k * 15)
    smoke_flourish(ink, (cx - 0.1, cy - 0.05), stops, strands=3, height=0.2, phase=1.2)
    if "crystal" in low:
        for i in range(3):
            crystal(
                ink, size * (0.4 + i * 0.1), size * 0.35, size * 0.04, size * 0.015,
                stops, fill_alpha=100,
            )
    placeholder_tag(ink, 10)
    return ink.img


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

def render_illustration(
    layer_name: str,
    key: str,
    trait_name: str,
    series: str | None,
    body_variant: str | None,
    pose: str | None,
    out_px: int,
) -> Image.Image:
    work = min(WORK_PX, out_px)
    if layer_name == "sky":
        img = draw_sky(key, trait_name, work)
    elif layer_name == "sea":
        img = draw_sea(key, trait_name, work)
    elif layer_name == "scene_element":
        img = draw_scene(key, trait_name, work, series)
    elif layer_name == "ship_class":
        img = draw_ship(key, trait_name, work)
    elif layer_name == "ship_condition":
        img = draw_condition(key, trait_name, work)
    elif layer_name == "body":
        img = draw_body(key, body_variant or "Green", pose or "Standing", work)
    elif layer_name == "clothing":
        img = draw_clothing(key, trait_name, work)
    elif layer_name == "eyes":
        img = draw_eyes(key, trait_name, work)
    elif layer_name == "mouth":
        img = draw_mouth(key, trait_name, work)
    elif layer_name == "hat":
        img = draw_hat(key, trait_name, work)
    elif layer_name == "aura":
        img = draw_aura(key, trait_name, work)
    else:
        raise ValueError(f"no renderer for layer {layer_name}")
    if work != out_px:
        img = img.resize((out_px, out_px), Image.LANCZOS)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument(
        "--profile", choices=["pixel", "illustration"], default=None,
        help="target render profile (default: config/render.json active_profile)",
    )
    ap.add_argument(
        "--only-layer", default=None,
        help="regenerate a single layer name (faster style iteration)",
    )
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
        if args.only_layer and layer.name != args.only_layer:
            continue
        ldir = SPRITES / layer.name
        ldir.mkdir(parents=True, exist_ok=True)
        jobs: list[tuple[str, str, str | None, str | None, str | None]] = []
        if layer.sprite_pattern:
            pose_layer = cfg.layer_by_name["pose"]
            for t in layer.traits:
                for p in pose_layer.traits:
                    rel = layer.sprite_pattern.format(
                        body=_snake(t.name), pose=_snake(p.name),
                    )
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
                img = render_illustration(
                    layer.name, key, trait_name, series, variant, pose, out_px,
                )
            img.save(path, optimize=True)
            written += 1

        lines = [
            f"# sprites/{layer.name} — {layer.display_name}",
            "",
            f"z-order: {layer.z_order} | required: {layer.required} | "
            f"dimensions: {out_px}x{out_px} RGBA PNG ({profile_name} profile)",
            "",
            "> **PLACEHOLDERS**: procedural Amano-ink stand-ins (gradient linework",
            "> on transparent ground; corner checker tag). Match ships_amano/ +",
            "> docs/art-reference/ART-DIRECTION.md and CLAUDE-STYLE-PACK.md.",
            "> Replace file-for-file with final art; filenames must not change.",
            "",
            "| file | trait |",
            "|---|---|",
        ]
        lines += [f"| `{f}` | {dsc} |" for f, dsc, *_ in jobs]
        (ldir / "README.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
        )

    log.info(
        "placeholders (%s profile, %dpx): %d written, %d kept",
        profile_name, out_px, written, skipped,
    )
    return 0


def _snake(name: str) -> str:
    import re
    s = name.lower().replace("'", "").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r" +", "_", s.strip())


if __name__ == "__main__":
    sys.exit(main())
