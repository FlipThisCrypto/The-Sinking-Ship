# SPDX-License-Identifier: MIT
"""Sky layer renderer (z-order 1 — the furthest-back plate).

Composition contract, shared by every sky trait:

* The plate is **atmosphere, not a block**. Alpha peaks in the upper third and
  decays to zero just past ``HORIZON`` so the ``sea`` plate (z-order 2) meets it
  without a seam and the bone-white ground still breathes through the middle.
* Colour lives on a vertical ramp; the same warped-noise field that drives the
  wash also supplies the cloud linework via ``ink.contour_strokes``, so form and
  edge always agree.
* A per-trait *signature motif* (moon, bolt, curtain, corona, meteor) carries
  the trait identity at thumbnail size — the rarity has to be legible at 128 px.

Alpha ceilings are deliberately conservative: the ship and character linework
composites on top of this, and a heavy sky is what makes a layered NFT look
muddy. ``MAX_ALPHA`` caps every plate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field as dc_field
from typing import Callable, Sequence

import numpy as np

from . import ink
from .core import (
    Canvas,
    blur,
    domain_warp,
    fbm,
    load_palette,
    ramp_image,
    rng_for,
    smoothstep,
)

PAL = load_palette()
HORIZON = 0.58
MAX_ALPHA = 0.86
"""Hard ceiling on sky opacity — protects legibility of the layers above."""


def _c(*names: str) -> list[tuple[int, int, int]]:
    return [PAL[n] for n in names]


@dataclass(frozen=True)
class SkySpec:
    """Declarative description of one sky trait."""

    key: str
    stops: list[tuple[int, int, int]]
    """Vertical ramp, top -> horizon."""
    wash_peak: float = 0.55
    """Alpha at the top of the plate before cloud modulation."""
    cloud_cells: int = 3
    cloud_octaves: int = 6
    warp: float = 120.0
    cloud_contrast: float = 0.55
    """0 = smooth haze, 1 = hard-edged cumulus."""
    line_level: float = 0.62
    line_width: float = 3.4
    line_alpha: float = 0.72
    ink_color: str = "deep_ink"
    horizon_glow: float = 0.0
    """Warm bloom sitting on the waterline (sunsets, fire)."""
    motif: Callable[["SkyCtx"], None] | None = None
    notes: str = ""
    extras: dict = dc_field(default_factory=dict)


@dataclass
class SkyCtx:
    """Mutable drawing context handed to a motif callback."""

    spec: SkySpec
    size: int
    rng: np.random.Generator
    canvas: Canvas
    ramp: np.ndarray
    cloud: np.ndarray

    @property
    def h(self) -> int:
        return self.size

    def ink_mask(self) -> np.ndarray:
        return np.zeros((self.size, self.size), dtype=np.float32)

    def paint(self, mask: np.ndarray, color: Sequence[float] | np.ndarray,
              alpha_scale: float = 1.0) -> None:
        self.canvas.over(np.broadcast_to(np.asarray(color, dtype=np.float32),
                                         (self.size, self.size, 3))
                         if np.ndim(color) == 1 else color,
                         np.clip(mask * alpha_scale, 0.0, 1.0))


# ---------------------------------------------------------------- motifs


def _disc(ctx: SkyCtx, cx: float, cy: float, r: float, color, alpha: float,
          rim: float = 0.0, rim_color=None) -> None:
    ys, xs = np.mgrid[0:ctx.size, 0:ctx.size].astype(np.float32)
    d = np.hypot(xs - cx, ys - cy)
    body = smoothstep(r, r - max(2.0, r * 0.02), d) * alpha
    ctx.paint(body, color)
    if rim > 0:
        edge = (smoothstep(r + rim, r, d) - smoothstep(r, r - rim * 0.35, d))
        ctx.paint(np.clip(edge, 0, 1), rim_color if rim_color is not None else color, 0.9)


def _halo(ctx: SkyCtx, cx: float, cy: float, r: float, color,
          alpha: float, falloff: float = 2.2) -> None:
    ys, xs = np.mgrid[0:ctx.size, 0:ctx.size].astype(np.float32)
    d = np.hypot(xs - cx, ys - cy) / max(1.0, r)
    ctx.paint(np.clip(1.0 - d, 0, 1) ** falloff * alpha, color)


def motif_moon(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    cx, cy, r = s * 0.70, s * 0.20, s * 0.085
    _halo(ctx, cx, cy, r * 5.2, PAL["pale_blue"], 0.30)
    _disc(ctx, cx, cy, r, PAL["bone_white"], 0.92)
    # bite out a crescent with the sky's own dark
    ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.hypot(xs - (cx - r * 0.46), ys - (cy - r * 0.20))
    ctx.paint(smoothstep(r * 0.98, r * 0.94, d) * 0.94, PAL["deep_navy"])
    m = ctx.ink_mask()
    ink.star_field(m, rng, 210, y_range=(0.02, 0.46), size_range=(0.7, 2.0))
    ctx.paint(ink.glow(m, 9.0, 0.45), PAL["bone_white"], 0.78)


def motif_sun(ctx: SkyCtx) -> None:
    s = ctx.size
    warm = ctx.spec.extras.get("sun_color", PAL["pale_gold"])
    cx, cy, r = s * 0.5, s * (HORIZON - 0.035), s * 0.115
    _halo(ctx, cx, cy, r * 6.4, warm, 0.46, falloff=1.7)
    # bright core + warm rim: a sand disc on a gold wash has no contrast
    _disc(ctx, cx, cy, r, PAL["bone_white"], 0.95, rim=r * 0.14, rim_color=warm)
    m = ctx.ink_mask()
    for i in range(26):
        a = -math.pi + i * math.pi / 25.0
        ink.polyline(m, [(cx, cy), (cx + math.cos(a) * s * 0.62,
                                    cy + math.sin(a) * s * 0.40)], 2.0, 0.30)
    ctx.paint(blur(m, 5.0) * 0.55, warm, 0.5)


def motif_rain(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    slant = float(rng.uniform(0.20, 0.30))
    for _ in range(1500):
        x = float(rng.uniform(-s * 0.2, s * 1.1))
        y = float(rng.uniform(0, s * (HORIZON + 0.06)))
        ln = float(rng.uniform(s * 0.020, s * 0.062))
        ink.polyline(m, [(x, y), (x + ln * slant, y + ln)],
                     float(rng.uniform(0.9, 1.9)), float(rng.uniform(0.35, 0.85)))
    fade = smoothstep(HORIZON + 0.06, HORIZON - 0.34,
                      np.linspace(0, 1, s, dtype=np.float32))[:, None]
    ctx.paint(m * fade, PAL["steel_blue"], 0.62)


def motif_bolt(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()

    def fork(x: float, y: float, dx: float, ylimit: float, w: float, depth: int) -> None:
        pts = [(x, y)]
        while y < ylimit and w > 0.6:
            step = float(rng.uniform(s * 0.028, s * 0.062))
            x += float(rng.uniform(-1, 1)) * step * 0.62 + dx * step * 0.35
            y += step
            pts.append((x, y))
            if depth < 3 and rng.random() < 0.24:
                fork(x, y, float(rng.uniform(-1.4, 1.4)),
                     y + (ylimit - y) * float(rng.uniform(0.3, 0.7)), w * 0.5, depth + 1)
        ink.calligraphic_stroke(m, pts, w, w * 0.35, taper=1.1)

    for k in range(2):
        fork(s * (0.34 + 0.30 * k) + float(rng.uniform(-60, 60)), s * 0.05,
             float(rng.uniform(-0.6, 0.6)), s * (HORIZON - 0.02),
             7.0 - 2.0 * k, 0)
    ctx.paint(ink.glow(m, 26.0, 0.85), PAL["bone_white"], 0.95)
    ctx.paint(blur(m, 90.0) * 0.5, PAL["lavender"], 0.55)


def motif_aurora(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    cols = [PAL[n] for n in ctx.spec.extras.get(
        "curtain", ("lavender", "amethyst", "pale_blue"))]
    # A curtain is an undulating horizontal *spine* with near-vertical rays
    # hanging from it. Two envelopes keep it from becoming a rectangular smear:
    # `side` fades the band out at both ends, and `drape` varies ray length
    # smoothly so the lower edge is ragged rather than ruled.
    for band in range(4):
        m = ctx.ink_mask()
        span = s * float(rng.uniform(0.55, 1.05))
        x0 = s * float(rng.uniform(-0.15, 0.55))
        sky_y = s * float(rng.uniform(0.05, 0.24))
        arc = s * float(rng.uniform(0.03, 0.09))
        arc_phase = float(rng.uniform(0, 2 * math.pi))
        drop = s * float(rng.uniform(0.16, 0.34))
        lean = float(rng.uniform(-0.16, 0.16))
        drape_phase = float(rng.uniform(0, 2 * math.pi))
        rays = int(span / s * 150)
        for ray in range(rays):
            u = ray / max(1.0, rays - 1.0)
            side = math.sin(math.pi * u) ** 0.7
            if side < 0.05:
                continue
            fx = x0 + u * span + float(rng.uniform(-3, 3))
            fy = sky_y + math.sin(u * 2.6 * math.pi + arc_phase) * arc
            drape = (0.55 + 0.45 * math.sin(u * 5.5 * math.pi + drape_phase)) * side
            length = drop * (0.35 + 0.65 * drape)
            pts = [(fx + lean * length * t + math.sin(t * 2.2) * s * 0.006,
                    fy + length * t) for t in (i / 12.0 for i in range(13))]
            ink.calligraphic_stroke(m, pts, 4.6, 0.9, taper=0.7,
                                    intensity=side * float(rng.uniform(0.5, 1.0)))
        col = cols[band % len(cols)]
        # keep the sharp pass genuinely sharp: the vertical striation IS the
        # read on an aurora, and it is the first thing a wide blur destroys
        ctx.paint(blur(m, 2.0) * 1.0, col, 0.60)
        ctx.paint(blur(m, 34.0) * 0.9, col, 0.28)
    m = ctx.ink_mask()
    ink.star_field(m, rng, 170, y_range=(0.01, 0.42), size_range=(0.6, 1.7))
    ctx.paint(ink.glow(m, 7.0, 0.4), PAL["bone_white"], 0.7)


def motif_meteors(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    stars = ctx.ink_mask()
    ink.star_field(stars, rng, 300, y_range=(0.0, 0.48), size_range=(0.6, 1.8))
    ctx.paint(ink.glow(stars, 8.0, 0.4), PAL["bone_white"], 0.72)
    # Long, fine, near-parallel streaks with a slight fan — a shower reads as a
    # radiant, so a shared angle with small jitter beats independent angles.
    base_ang = 0.72
    for i in range(24):
        m = ctx.ink_mask()
        x = float(rng.uniform(-s * 0.15, s * 1.05))
        y = float(rng.uniform(-s * 0.08, s * 0.34))
        ln = float(rng.uniform(s * 0.14, s * 0.42))
        ang = base_ang + float(rng.uniform(-0.10, 0.10))
        head = (x + math.cos(ang) * ln, y + math.sin(ang) * ln)
        ink.calligraphic_stroke(m, ink.catmull_rom([(x, y), (
            (x + head[0]) / 2 + float(rng.uniform(-10, 10)),
            (y + head[1]) / 2), head]), 0.6, 3.4, taper=2.4)
        ctx.paint(ink.glow(m, 7.0, 0.55), PAL["bone_white"], 0.95)
        ctx.paint(blur(m, 26.0) * 0.7,
                  PAL["pale_gold"] if i % 3 else PAL["coral"], 0.34)


def motif_blood_moon(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    cx, cy, r = s * 0.5, s * 0.235, s * 0.165
    _halo(ctx, cx, cy, r * 4.6, PAL["blood_red"], 0.46, falloff=1.8)
    _disc(ctx, cx, cy, r, PAL["maroon"], 0.90, rim=r * 0.09,
          rim_color=PAL["crimson"])
    # cloud drawn ACROSS the disc, so the moon sits in the weather, not on it
    m = ctx.ink_mask()
    for i in range(7):
        y = s * float(rng.uniform(0.08, 0.44))
        ink.tendril(m, -s * 0.05, y, s * float(rng.uniform(0.45, 0.95)),
                    float(rng.uniform(-0.16, 0.16)), rng,
                    width=float(rng.uniform(3.0, 5.5)),
                    curl_radius=float(rng.uniform(0.05, 0.13)), sway=0.30)
    ctx.paint(m, PAL["ink_black"], 0.52)


def motif_fire(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    ink.sparks(m, rng, 420, y_range=(0.06, HORIZON + 0.01),
               size=(1.8, 5.6) if s >= 1024 else (1.0, 3.2), rise=2.4)
    ctx.paint(ink.glow(m, 10.0, 0.6), PAL["pale_gold"], 0.80)
    curls = ctx.ink_mask()
    for i in range(11):
        # flame tongues climb, so tendrils launch upward off the waterline
        ink.tendril(curls, s * float(rng.uniform(0.02, 0.98)),
                    s * float(rng.uniform(0.34, HORIZON)),
                    s * float(rng.uniform(0.22, 0.46)),
                    -math.pi / 2 + float(rng.uniform(-0.7, 0.7)), rng,
                    width=float(rng.uniform(3.8, 6.0)),
                    curl_radius=float(rng.uniform(0.10, 0.22)), sway=0.55)
    ctx.paint(curls, PAL["blood_red"], 0.52)


def motif_eclipse(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    cx, cy, r = s * 0.5, s * 0.30, s * 0.150
    _halo(ctx, cx, cy, r * 5.8, PAL["pale_gold"], 0.42, falloff=1.5)
    # Corona: irregular ray lengths clustered by a low-frequency envelope, so
    # it reads as plasma rather than a sunflower.
    m = ctx.ink_mask()
    lobe_phase = float(rng.uniform(0, 2 * math.pi))
    for i in range(190):
        a = i / 190.0 * 2 * math.pi + float(rng.uniform(-0.012, 0.012))
        lobe = 0.62 + 0.38 * (0.5 + 0.5 * math.sin(a * 3 + lobe_phase))
        ln = r * (1.05 + (1.55 * lobe) * float(rng.uniform(0.35, 1.0)))
        ink.calligraphic_stroke(m, [
            (cx + math.cos(a) * r * 1.01, cy + math.sin(a) * r * 1.01),
            (cx + math.cos(a) * ln, cy + math.sin(a) * ln)],
            2.4, 0.4, taper=1.8, intensity=float(rng.uniform(0.45, 1.0)))
    ctx.paint(ink.glow(m, 20.0, 0.75), PAL["sand"], 0.78)
    # bright limb then the occulting disc
    ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.hypot(xs - cx, ys - cy)
    ring = np.clip(smoothstep(r * 1.10, r * 1.00, d) - smoothstep(r * 1.00, r * 0.965, d), 0, 1)
    ctx.paint(ring, PAL["bone_white"], 1.0)
    ctx.paint(smoothstep(r, r * 0.97, d), PAL["ink_black"], 0.985)
    stars = ctx.ink_mask()
    ink.star_field(stars, rng, 130, y_range=(0.0, 0.46), size_range=(0.6, 1.6))
    ctx.paint(ink.glow(stars, 7.0, 0.4), PAL["bone_white"], 0.55)


def motif_fog_veils(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    for _ in range(9):
        m = ctx.ink_mask()
        y = float(rng.uniform(0.10, HORIZON)) * s
        amp = float(rng.uniform(s * 0.006, s * 0.022))
        ink.wave_ribbon(m, y, s, rng, amplitude=amp,
                        wavelength=float(rng.uniform(s * 0.5, s * 1.4)),
                        width=float(rng.uniform(4.0, 11.0)), crest_curls=0)
        ctx.paint(blur(m, float(rng.uniform(18, 46))) * 0.9, PAL["bone_white"], 0.55)


def motif_cirrus(ctx: SkyCtx) -> None:
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    for _ in range(16):
        y = float(rng.uniform(0.04, 0.40)) * s
        x0 = float(rng.uniform(-0.1, 0.7)) * s
        span = float(rng.uniform(0.25, 0.65)) * s
        pts = ink.catmull_rom([
            (x0 + span * t, y + math.sin(t * math.pi * float(rng.uniform(1, 2.4)))
             * s * float(rng.uniform(0.004, 0.016)))
            for t in np.linspace(0, 1, 7)])
        ink.calligraphic_stroke(m, pts, float(rng.uniform(2.0, 4.5)), 0.6, taper=1.3)
    ctx.paint(blur(m, 4.0), PAL["bone_white"], 0.60)
    ctx.paint(blur(m, 30.0) * 0.7, PAL["pale_blue"], 0.35)


def motif_storm_curls(ctx: SkyCtx) -> None:
    """Rolling storm front: long travelling tendrils that curl where they end."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    for i in range(9):
        side = -0.08 if i % 2 == 0 else 1.08
        y = s * float(rng.uniform(0.03, 0.46))
        ang = float(rng.uniform(-0.28, 0.28)) + (0.0 if i % 2 == 0 else math.pi)
        ink.tendril(m, s * side, y, s * float(rng.uniform(0.40, 0.85)), ang, rng,
                    width=float(rng.uniform(3.5, 6.5)),
                    curl_radius=float(rng.uniform(0.08, 0.18)), sway=0.42)
    for _ in range(4):
        ink.curl_flourish(m, float(rng.uniform(0.12, 0.88)) * s,
                          float(rng.uniform(0.06, 0.40)) * s,
                          float(rng.uniform(s * 0.03, s * 0.075)), rng,
                          turns=float(rng.uniform(1.4, 2.4)), width=3.2)
    ctx.paint(m, PAL["deep_violet"], 0.62)
    ctx.paint(blur(m, 40.0) * 0.7, PAL["amethyst"], 0.30)


# ------------------------------------------------------------------ specs

SKY_SPECS: dict[str, SkySpec] = {
    "calm_blue": SkySpec(
        "calm_blue", _c("steel_blue", "pale_blue", "bone_white"),
        wash_peak=0.56, cloud_cells=2, warp=90.0, cloud_contrast=0.34,
        line_level=0.70, line_width=2.4, line_alpha=0.32, ink_color="steel_blue",
        motif=motif_cirrus, notes="high thin cirrus, generous white"),
    "overcast": SkySpec(
        "overcast", _c("slate_gray", "ash_gray", "bone_white"),
        wash_peak=0.70, cloud_cells=3, warp=150.0, cloud_contrast=0.54,
        line_level=0.56, line_width=3.8, line_alpha=0.44, ink_color="slate_gray",
        notes="flat pressing cloud deck"),
    "orange_sunset": SkySpec(
        "orange_sunset", _c("ember_orange", "coral", "sand"),
        wash_peak=0.66, cloud_cells=2, warp=170.0, cloud_contrast=0.58,
        line_level=0.60, line_width=3.8, line_alpha=0.60, ink_color="maroon",
        horizon_glow=0.55, motif=motif_sun,
        extras={"sun_color": PAL["ember_orange"]}),
    "golden_sunset": SkySpec(
        "golden_sunset", _c("gold", "pale_gold", "sand"),
        wash_peak=0.62, cloud_cells=2, warp=150.0, cloud_contrast=0.50,
        line_level=0.62, line_width=3.4, line_alpha=0.52, ink_color="bronze",
        horizon_glow=0.68, motif=motif_sun,
        extras={"sun_color": PAL["pale_gold"]}),
    "moonlit": SkySpec(
        "moonlit", _c("deep_navy", "navy", "steel_blue"),
        wash_peak=0.74, cloud_cells=3, warp=140.0, cloud_contrast=0.44,
        line_level=0.64, line_width=3.0, line_alpha=0.44, ink_color="abyss_navy",
        motif=motif_moon),
    "heavy_rain": SkySpec(
        "heavy_rain", _c("shadow_navy", "slate_gray", "steel_blue"),
        wash_peak=0.70, cloud_cells=3, warp=190.0, cloud_contrast=0.52,
        line_level=0.60, line_width=4.0, line_alpha=0.50, ink_color="deep_ink",
        motif=motif_rain),
    "fog": SkySpec(
        "fog", _c("ash_gray", "bone_white", "bone_white"),
        wash_peak=0.66, cloud_cells=2, warp=70.0, cloud_contrast=0.26,
        line_level=0.72, line_width=2.4, line_alpha=0.22, ink_color="slate_gray",
        motif=motif_fog_veils, notes="lowest contrast plate in the set"),
    "lightning": SkySpec(
        "lightning", _c("deep_ink", "deep_violet", "slate_gray"),
        wash_peak=0.80, cloud_cells=3, warp=200.0, cloud_contrast=0.62,
        line_level=0.58, line_width=4.2, line_alpha=0.58, ink_color="ink_black",
        motif=motif_bolt),
    "purple_storm": SkySpec(
        "purple_storm", _c("deep_violet", "violet", "amethyst"),
        wash_peak=0.78, cloud_cells=2, warp=230.0, cloud_contrast=0.66,
        line_level=0.56, line_width=4.4, line_alpha=0.62, ink_color="deep_violet",
        motif=motif_storm_curls),
    "aurora": SkySpec(
        "aurora", _c("abyss_navy", "deep_navy", "navy"),
        wash_peak=0.80, cloud_cells=2, warp=110.0, cloud_contrast=0.30,
        line_level=0.72, line_width=2.4, line_alpha=0.26, ink_color="deep_ink",
        motif=motif_aurora,
        extras={"curtain": ("lavender", "amethyst", "pale_blue")}),
    "green_aurora": SkySpec(
        "green_aurora", _c("abyss_navy", "deep_teal", "teal_green"),
        wash_peak=0.80, cloud_cells=2, warp=110.0, cloud_contrast=0.30,
        line_level=0.72, line_width=2.4, line_alpha=0.26, ink_color="deep_ink",
        motif=motif_aurora,
        extras={"curtain": ("bright_green", "chia_green", "pale_green")},
        notes="Chia-coded twin of aurora"),
    "meteor_shower": SkySpec(
        "meteor_shower", _c("ink_black", "abyss_navy", "deep_navy"),
        wash_peak=0.84, cloud_cells=2, warp=90.0, cloud_contrast=0.26,
        line_level=0.76, line_width=2.2, line_alpha=0.22, ink_color="ink_black",
        motif=motif_meteors),
    "blood_moon": SkySpec(
        "blood_moon", _c("maroon", "blood_red", "crimson"),
        wash_peak=0.80, cloud_cells=2, warp=210.0, cloud_contrast=0.58,
        line_level=0.58, line_width=4.2, line_alpha=0.58, ink_color="ink_black",
        motif=motif_blood_moon),
    "fire_sky": SkySpec(
        "fire_sky", _c("blood_red", "crimson", "ember_orange"),
        wash_peak=0.82, cloud_cells=2, warp=250.0, cloud_contrast=0.70,
        line_level=0.55, line_width=4.6, line_alpha=0.62, ink_color="maroon",
        horizon_glow=0.60, motif=motif_fire),
    "solar_eclipse": SkySpec(
        "solar_eclipse", _c("ink_black", "deep_ink", "shadow_navy"),
        wash_peak=0.86, cloud_cells=2, warp=120.0, cloud_contrast=0.34,
        line_level=0.74, line_width=2.6, line_alpha=0.28, ink_color="ink_black",
        motif=motif_eclipse, notes="the legendary; brightest corona in the set"),
}


# ----------------------------------------------------------------- render


def _alpha_profile(size: int, peak: float) -> np.ndarray:
    """Top-weighted vertical alpha envelope that reaches 0 just past HORIZON.

    Weighted hard toward the crown: the golden references are ~75% near-white,
    so the plate has to surrender the middle of the frame rather than tint it.
    """
    y = np.linspace(0.0, 1.0, size, dtype=np.float32)
    band = smoothstep(HORIZON + 0.02, HORIZON - 0.46, y)
    crown = 0.34 + 0.66 * smoothstep(0.40, 0.0, y)
    return (band * crown * peak)[:, None]


def render(trait_key: str, size: int = 2048) -> Canvas:
    """Render one sky plate. Deterministic in ``trait_key``."""
    spec = SKY_SPECS[trait_key]
    rng = rng_for(f"sky/{trait_key}/v2")
    canvas = Canvas(size)

    ramp = ramp_image(spec.stops, size, size, 0.0, HORIZON)

    # --- cloud field: warped fBm, contrast-shaped into form
    base = fbm(size, size, rng, octaves=spec.cloud_octaves, cells=spec.cloud_cells,
               gain=0.52, lacunarity=2.05)
    cloud = domain_warp(base, rng, amount=spec.warp, cells=3)
    # squash vertically so cloud reads as horizontal weather, not blobs
    cloud = cv2_vsquash(cloud, 0.55)
    lo = 0.5 - spec.cloud_contrast * 0.5
    hi = 0.5 + spec.cloud_contrast * 0.5
    shaped = smoothstep(lo, hi, cloud)

    env = _alpha_profile(size, spec.wash_peak)
    wash = env * (0.55 + 0.45 * shaped)
    canvas.over(ramp, np.clip(wash, 0.0, 1.0))

    ctx = SkyCtx(spec=spec, size=size, rng=rng, canvas=canvas, ramp=ramp, cloud=cloud)

    # --- horizon bloom (sunsets, fire): warm light sitting on the waterline
    if spec.horizon_glow > 0:
        y = np.linspace(0.0, 1.0, size, dtype=np.float32)
        band = np.exp(-((y - (HORIZON - 0.015)) / 0.085) ** 2)[:, None]
        ctx.paint(np.broadcast_to(band, (size, size)) * spec.horizon_glow,
                  PAL["sand"])

    # --- cloud edge linework, drawn from the same field as the wash.
    # Few, wide, open arcs only: closed loops and small blobs read as scribble.
    if spec.line_alpha > 0.02:
        lines = np.zeros((size, size), dtype=np.float32)
        ink.contour_strokes(lines, cloud, spec.line_level, width=spec.line_width,
                            max_contours=7, smooth=size * 0.016,
                            min_area_frac=0.020, prefer_wide=1.35,
                            arc_frac=0.62, rng=rng)
        ink.contour_strokes(lines, cloud, spec.line_level + 0.16,
                            width=spec.line_width * 0.55, max_contours=5,
                            smooth=size * 0.013, min_area_frac=0.010,
                            prefer_wide=1.1, arc_frac=0.5, intensity=0.65,
                            rng=rng)
        lines = ink.ink_texture(lines, rng, cells=180, depth=0.22)
        ctx.paint(lines * _alpha_profile(size, 1.0), PAL[spec.ink_color],
                  spec.line_alpha)

    if spec.motif is not None:
        spec.motif(ctx)

    # --- clamp: the sky must never dominate the layers stacked above it,
    # and must be clear of the waterline so `sea` seats without a seam.
    y = np.linspace(0.0, 1.0, size, dtype=np.float32)
    canvas.multiply_alpha(smoothstep(HORIZON + 0.075, HORIZON - 0.02, y)[:, None])
    canvas.multiply_alpha(MAX_ALPHA)
    return canvas


def cv2_vsquash(field: np.ndarray, factor: float) -> np.ndarray:
    """Vertically compress a noise field so forms read as horizontal weather."""
    import cv2

    h, w = field.shape[:2]
    small = cv2.resize(field, (w, max(2, int(h * factor))),
                       interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)


def all_keys() -> list[str]:
    return list(SKY_SPECS)
