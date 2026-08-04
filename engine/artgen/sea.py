# SPDX-License-Identifier: MIT
"""Sea layer renderer (z-order 2 — the plate the sky hands off to).

Composition contract:

* The sea is a **band, not a floor**. Alpha rises at the waterline, peaks just
  below it, and decays out before the bottom edge. That is the reference
  grammar (`ships_amano/`, `docs/art-reference/`): the vessel floats on a belt
  of churning ink with bone-white beneath it, never on a filled rectangle.
  It is also a layering requirement — the character's lower body dissolves into
  water tendrils across the bottom-centre of the frame, and a filled sea there
  turns the composite to mud.
* Waves are drawn in **perspective**: rows compress and thin toward the
  horizon, widen and thicken toward the viewer. Evenly spaced rows read as
  wallpaper.
* Every row is a `ink.flow_bundle` — nested parallel curves that pinch shut at
  the ends — with curling crests. A single sine line reads as a graph.
* A thin calligraphic **waterline** anchors the composition where sky meets sea.

Lengths are in master-reference pixels and pass through ``SeaCtx.px``.
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
    load_palette,
    master_scale,
    ramp_image,
    rng_for,
    smoothstep,
    value_noise,
)

PAL = load_palette()
HORIZON = 0.58
ROW_FRONT = 0.895
"""y of the frontmost wave row. The alpha envelope must outlast it."""
MAX_ALPHA = 0.88


def _c(*names: str) -> list[tuple[int, int, int]]:
    return [PAL[n] for n in names]


@dataclass(frozen=True)
class SeaSpec:
    """Declarative description of one sea trait."""

    key: str
    stops: list[tuple[int, int, int]]
    """Vertical ramp across the band, waterline -> deep."""
    wash_peak: float = 0.40
    """Alpha of the water tint at the band's strongest row."""
    depth_bias: float = 0.0
    """-1 hugs the waterline, +1 sinks the weight toward the bottom edge."""
    rows: int = 9
    amplitude: float = 62.0
    """Swell height of the frontmost row, master-reference px."""
    line_width: float = 5.2
    line_alpha: float = 0.70
    ink_color: str = "deep_navy"
    crest_curls: int = 2
    """Curling crests per row — the Hokusai claw."""
    spray: int = 0
    waterline: float = 0.55
    """Alpha of the horizon rule; 0 omits it."""
    motif: Callable[["SeaCtx"], None] | None = None
    notes: str = ""
    extras: dict = dc_field(default_factory=dict)


@dataclass
class SeaCtx:
    spec: SeaSpec
    size: int
    rng: np.random.Generator
    canvas: Canvas
    band: np.ndarray
    """Vertical alpha envelope of the water band, shape (size, 1)."""

    @property
    def k(self) -> float:
        return master_scale(self.size)

    def px(self, value: float) -> float:
        return value * self.k

    def soft(self, mask: np.ndarray, sigma: float) -> np.ndarray:
        return blur(mask, self.px(sigma))

    def ink_mask(self) -> np.ndarray:
        return np.zeros((self.size, self.size), dtype=np.float32)

    def paint(self, mask: np.ndarray, color: Sequence[float] | np.ndarray,
              alpha_scale: float = 1.0) -> None:
        rgb = (np.broadcast_to(np.asarray(color, dtype=np.float32),
                               (self.size, self.size, 3))
               if np.ndim(color) == 1 else color)
        self.canvas.over(rgb, np.clip(mask * alpha_scale, 0.0, 1.0))

    def row_y(self, t: float) -> float:
        """Canvas y for a wave row, ``t`` 0 at the horizon and 1 at the front.

        The ``t ** 1.55`` easing is the perspective: rows bunch up near the
        horizon and spread toward the viewer.
        """
        return self.size * (HORIZON + (ROW_FRONT - HORIZON) * (t ** 1.55))


# ----------------------------------------------------------------- helpers


def _swell(ctx: SeaCtx, mask: np.ndarray, y: float, amp: float, width: float,
           curls: int, *, wavelength: float | None = None) -> None:
    """One wave row, drawn as 2–4 **broken** swells rather than one long line.

    A wave line that runs the full width at a constant y reads as a contour on
    a topographic map. Real swells are segments: they rise, break, and are
    overlapped by the next one. Each segment gets its own phase and vertical
    offset so the row never resolves into a single ruled curve.
    """
    s, rng = ctx.size, ctx.rng
    for _ in range(int(rng.integers(2, 5))):
        wl = wavelength if wavelength is not None else s * float(rng.uniform(0.30, 0.62))
        phase = float(rng.uniform(0, 2 * math.pi))
        x0 = float(rng.uniform(-0.15, 0.62)) * s
        span = float(rng.uniform(0.38, 0.92)) * s
        dy = amp * float(rng.uniform(-0.55, 0.55))
        spine = [
            (x, y + dy
             + math.sin(x / wl * 2 * math.pi + phase) * amp
             + math.sin(x / (wl * 0.41) * 2 * math.pi + phase * 1.7) * amp * 0.30)
            for x in np.linspace(x0, x0 + span, 120)
        ]
        ink.flow_bundle(mask, spine, rng, count=int(rng.integers(3, 6)),
                        spread=amp * 0.42, width=width, pinch=0.55)
        for _ in range(curls):
            i = int(rng.integers(16, len(spine) - 16))
            cx, cy = spine[i]
            r = amp * float(rng.uniform(0.55, 1.15))
            ink.curl_flourish(mask, cx, cy - r * 0.7, r, rng,
                              turns=float(rng.uniform(1.2, 2.1)),
                              width=width * 0.85)


def _band_envelope(size: int, peak: float, depth_bias: float,
                   rng: np.random.Generator) -> np.ndarray:
    """Alpha envelope: rises at the waterline, holds, then dissolves.

    Two properties matter and both were learned the hard way:

    * The fade-out must sit *below* the frontmost wave row (``ROW_FRONT``) or
      the nearest, largest swells are drawn into alpha that has already gone to
      zero — which reads as a thin strip of sea floating over empty white.
    * The fade must be **ragged**, not a ruled horizontal. A 1-D envelope ends
      the water on a dead-straight line across the frame, which is the single
      most artificial thing a hand-drawn sea can do. The lower edge is
      displaced per-column by low-frequency noise so the water gives out in an
      uneven, brushed hem.
    """
    y = np.linspace(0.0, 1.0, size, dtype=np.float32)[:, None]
    rise = smoothstep(HORIZON - 0.012, HORIZON + 0.045, y)
    # depth_bias slides where the band gives out: -1 fades early (hugs the
    # waterline), +1 carries almost to the bottom edge.
    fade_start = ROW_FRONT - 0.055 + 0.035 * depth_bias
    fade_end = fade_start + 0.20 + 0.05 * depth_bias
    hem = (value_noise(1, size, 5, rng)[0] - 0.5) * 0.085
    fall = smoothstep(fade_end + hem[None, :], fade_start + hem[None, :],
                      np.broadcast_to(y, (size, size)))
    return np.clip(rise * fall * peak, 0.0, 1.0)


# ------------------------------------------------------------------ motifs


def motif_spray(ctx: SeaCtx) -> None:
    """Airborne droplets over the crests — storm signature."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    for _ in range(ctx.spec.spray):
        x = float(rng.uniform(0, s))
        t = float(rng.random()) ** 0.7
        y = ctx.row_y(t) - float(rng.uniform(0, ctx.px(90)))
        r = ctx.px(float(rng.uniform(1.6, 5.0)))
        ink.polyline(m, [(x, y), (x + float(rng.uniform(-r, r)), y - r * 2.2)],
                     max(0.7, r * 0.5), float(rng.uniform(0.4, 1.0)))
    ctx.paint(m * ctx.band, PAL["bone_white"], 0.85)
    ctx.paint(ctx.soft(m, 14.0) * ctx.band * 0.7, PAL["pale_blue"], 0.45)


def motif_ice(ctx: SeaCtx) -> None:
    """Angular floes with a cracked seam network instead of swells."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    fills = ctx.ink_mask()
    for _ in range(17):
        t = float(rng.random()) ** 0.85
        cy = ctx.row_y(t)
        cx = float(rng.uniform(-0.05, 1.05)) * s
        r = ctx.px(float(rng.uniform(110, 330))) * (0.35 + 0.65 * t)
        n = int(rng.integers(5, 8))
        poly = []
        for i in range(n):
            a = i / n * 2 * math.pi + float(rng.uniform(-0.25, 0.25))
            rr = r * float(rng.uniform(0.6, 1.15))
            poly.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.42))
        ink.polyline(m, poly, ctx.px(3.6), 1.0, closed=True)
        if rng.random() < 0.45:
            ink.fill_poly(fills, poly, 1.0)
        # internal cracks
        for _ in range(int(rng.integers(1, 4))):
            i, j = int(rng.integers(0, n)), int(rng.integers(0, n))
            if i != j:
                ink.polyline(m, [poly[i], poly[j]], ctx.px(1.8), 0.6)
    ctx.paint(fills * ctx.band * 0.55, PAL["bone_white"], 0.7)
    ctx.paint(m * ctx.band, PAL["steel_blue"], 0.8)


def motif_whirl(ctx: SeaCtx) -> None:
    """Concentric spirals converging on a dark throat."""
    s, rng = ctx.size, ctx.rng
    cx, cy = s * 0.5, s * 0.79
    m = ctx.ink_mask()
    for arm in range(9):
        r0 = s * (0.035 + arm * 0.032)
        pts = ink.spiral(cx, cy, r0, r0 * 0.10,
                         turns=float(rng.uniform(1.05, 1.55)),
                         phase=arm * 0.7 + float(rng.uniform(-0.2, 0.2)),
                         samples=200, squash=0.40)
        ink.calligraphic_stroke(m, pts, ctx.px(6.0), ctx.px(1.2), taper=1.4)
    ctx.paint(m * ctx.band, PAL[ctx.spec.ink_color], 0.85)
    # the throat
    ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.hypot(xs - cx, (ys - cy) / 0.42)
    ctx.paint(smoothstep(s * 0.075, s * 0.018, d) * 0.72, PAL["ink_black"])


def motif_glass(ctx: SeaCtx) -> None:
    """Mirror-still: a horizontal sheen and a reflection, almost no wave."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    for i in range(14):
        y = ctx.row_y(float(rng.random()) ** 1.2)
        x0 = float(rng.uniform(-0.05, 0.55)) * s
        span = float(rng.uniform(0.25, 0.7)) * s
        ink.calligraphic_stroke(
            m, [(x0, y), (x0 + span * 0.5, y + ctx.px(float(rng.uniform(-3, 3)))),
                (x0 + span, y)],
            ctx.px(float(rng.uniform(2.4, 5.0))), ctx.px(0.8), taper=1.2)
    ctx.paint(m * ctx.band, PAL["pale_blue"], 0.75)
    # sheen: a soft bright bar just under the waterline
    y = np.linspace(0.0, 1.0, s, dtype=np.float32)
    sheen = np.exp(-((y - (HORIZON + 0.055)) / 0.030) ** 2)[:, None]
    ctx.paint(np.broadcast_to(sheen, (s, s)) * 0.42, PAL["bone_white"])


def motif_biolum(ctx: SeaCtx) -> None:
    """Cold light strung along the crests."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    for _ in range(30):
        t = float(rng.random()) ** 0.8
        y = ctx.row_y(t)
        x0 = float(rng.uniform(-0.05, 0.75)) * s
        span = float(rng.uniform(0.12, 0.42)) * s
        amp = ctx.px(14) * (0.3 + t)
        pts = [(x0 + span * u, y + math.sin(u * math.pi * 2.4) * amp)
               for u in np.linspace(0, 1, 30)]
        ink.calligraphic_stroke(m, pts, ctx.px(3.2), ctx.px(0.7), taper=1.3)
    ink.star_field(m, rng, 260, y_range=(HORIZON + 0.02, ROW_FRONT),
                   size_range=(ctx.px(2.0), ctx.px(6.0)), sparkle_frac=0.06)
    glow_col = PAL[ctx.spec.extras.get("glow", "bright_green")]
    ctx.paint(np.clip(m + ctx.soft(m, 8.0) * 0.7, 0, 1) * ctx.band * 1.6,
              PAL["pale_green"], 0.9)
    ctx.paint(ctx.soft(m, 42.0) * ctx.band * 1.3, glow_col, 0.55)


def motif_chia_tide(ctx: SeaCtx) -> None:
    """The mythic: green tide with gold filigree riding the crests."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    for _ in range(9):
        t = float(rng.random()) ** 0.9
        y = ctx.row_y(t)
        x = float(rng.uniform(0.04, 0.96)) * s
        r = ctx.px(float(rng.uniform(34, 96))) * (0.5 + 0.5 * t)
        ink.curl_flourish(m, x, y - r * 0.6, r, rng,
                          turns=float(rng.uniform(1.3, 2.4)), width=ctx.px(3.4))
    ctx.paint(m * ctx.band * 1.5, PAL["gold"], 0.85)
    ctx.paint(ctx.soft(m, 30.0) * ctx.band, PAL["pale_gold"], 0.42)


def motif_abyss_shafts(ctx: SeaCtx) -> None:
    """Light shafts failing downward — depth without filling the frame."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    for _ in range(11):
        x = float(rng.uniform(0.02, 0.98)) * s
        top = s * (HORIZON + 0.02)
        length = s * float(rng.uniform(0.10, 0.30))
        lean = float(rng.uniform(-0.16, 0.16))
        w = ctx.px(float(rng.uniform(14, 46)))
        ink.fill_poly(m, [(x - w, top), (x + w, top),
                          (x + w * 0.25 + lean * length, top + length),
                          (x - w * 0.25 + lean * length, top + length)], 1.0)
    ctx.paint(ctx.soft(m, 40.0) * ctx.band * 0.8, PAL["steel_blue"], 0.30)


# -------------------------------------------------------------------- specs

SEA_SPECS: dict[str, SeaSpec] = {
    "calm": SeaSpec(
        "calm", _c("pale_blue", "steel_blue", "sea_blue"),
        wash_peak=0.34, depth_bias=-0.15, rows=8, amplitude=34.0,
        line_width=4.4, line_alpha=0.58, ink_color="sea_blue",
        crest_curls=1, waterline=0.42,
        notes="the common tier: quietest plate, widest spacing"),
    "storm_swell": SeaSpec(
        "storm_swell", _c("steel_blue", "navy", "deep_navy"),
        wash_peak=0.44, depth_bias=0.25, rows=8, amplitude=104.0,
        line_width=6.4, line_alpha=0.66, ink_color="deep_navy",
        crest_curls=4, spray=520, waterline=0.5, motif=motif_spray),
    "black_sea": SeaSpec(
        "black_sea", _c("shadow_navy", "deep_ink", "ink_black"),
        wash_peak=0.66, depth_bias=0.15, rows=7, amplitude=70.0,
        line_width=6.0, line_alpha=0.70, ink_color="ink_black",
        crest_curls=2, waterline=0.6),
    "frozen": SeaSpec(
        "frozen", _c("bone_white", "pale_blue", "steel_blue"),
        wash_peak=0.36, depth_bias=0.05, rows=5, amplitude=18.0,
        line_width=3.2, line_alpha=0.38, ink_color="steel_blue",
        crest_curls=0, waterline=0.45, motif=motif_ice),
    "emerald_water": SeaSpec(
        "emerald_water", _c("pale_green", "chia_green", "teal_green"),
        wash_peak=0.42, depth_bias=0.0, rows=9, amplitude=58.0,
        line_width=5.0, line_alpha=0.66, ink_color="deep_teal",
        crest_curls=2, waterline=0.5),
    "red_water": SeaSpec(
        "red_water", _c("coral", "crimson", "maroon"),
        wash_peak=0.48, depth_bias=0.1, rows=9, amplitude=64.0,
        line_width=5.4, line_alpha=0.70, ink_color="maroon",
        crest_curls=3, waterline=0.55),
    "whirlpool": SeaSpec(
        "whirlpool", _c("steel_blue", "navy", "abyss_navy"),
        wash_peak=0.46, depth_bias=0.4, rows=6, amplitude=44.0,
        line_width=4.6, line_alpha=0.60, ink_color="abyss_navy",
        crest_curls=1, waterline=0.5, motif=motif_whirl),
    "glass_sea": SeaSpec(
        "glass_sea", _c("bone_white", "pale_blue", "steel_blue"),
        wash_peak=0.34, depth_bias=-0.25, rows=5, amplitude=10.0,
        line_width=3.0, line_alpha=0.34, ink_color="steel_blue",
        crest_curls=0, waterline=0.7, motif=motif_glass,
        notes="mirror-still, eerie — the stillest plate in the set"),
    "abyss": SeaSpec(
        "abyss", _c("deep_navy", "abyss_navy", "ink_black"),
        wash_peak=0.64, depth_bias=0.55, rows=8, amplitude=48.0,
        line_width=5.0, line_alpha=0.62, ink_color="ink_black",
        crest_curls=1, waterline=0.45, motif=motif_abyss_shafts),
    "bioluminescent": SeaSpec(
        "bioluminescent", _c("deep_ink", "abyss_navy", "deep_teal"),
        wash_peak=0.56, depth_bias=0.2, rows=9, amplitude=56.0,
        line_width=4.6, line_alpha=0.50, ink_color="deep_ink",
        crest_curls=2, waterline=0.4, motif=motif_biolum,
        extras={"glow": "bright_green"}),
    "chia_green_tide": SeaSpec(
        "chia_green_tide", _c("bright_green", "chia_green", "deep_teal"),
        wash_peak=0.50, depth_bias=0.05, rows=10, amplitude=76.0,
        line_width=5.6, line_alpha=0.74, ink_color="deep_teal",
        crest_curls=3, waterline=0.55, motif=motif_chia_tide,
        notes="mythic — the Chia-coded top of the ladder"),
}


# ------------------------------------------------------------------ render


def render(trait_key: str, size: int = 2048) -> Canvas:
    """Render one sea plate. Deterministic in ``trait_key``."""
    spec = SEA_SPECS[trait_key]
    rng = rng_for(f"sea/{trait_key}/v1")
    canvas = Canvas(size)
    band = _band_envelope(size, 1.0, spec.depth_bias, rng)

    ctx = SeaCtx(spec=spec, size=size, rng=rng, canvas=canvas, band=band)

    # --- water tint: a ramp confined to the band, textured so it is not flat
    ramp = ramp_image(spec.stops, size, size, HORIZON, ROW_FRONT)
    grain = value_noise(size, size, 7, rng)
    tint = band * spec.wash_peak * (0.72 + 0.28 * grain)
    canvas.over(ramp, np.clip(tint, 0.0, 1.0))

    # --- wave rows, front to back so nearer swells overlap farther ones
    waves = ctx.ink_mask()
    for i in range(spec.rows):
        t = 1.0 - i / max(1, spec.rows - 1)
        y = ctx.row_y(t)
        amp = ctx.px(spec.amplitude) * (0.16 + 0.84 * t)
        width = ctx.px(spec.line_width) * (0.34 + 0.66 * t)
        curls = spec.crest_curls if t > 0.28 else max(0, spec.crest_curls - 1)
        _swell(ctx, waves, y, amp, width, curls)
    waves = ink.ink_texture(waves, rng, cells=200, depth=0.20)
    ctx.paint(waves * band, PAL[spec.ink_color], spec.line_alpha)

    # --- waterline rule: the horizon needs an edge or sky and sea just blur
    if spec.waterline > 0.02:
        rule = ctx.ink_mask()
        y = size * HORIZON
        ink.calligraphic_stroke(
            rule,
            [(x, y + math.sin(x / (size * 0.6) * 2 * math.pi) * ctx.px(5.0))
             for x in np.linspace(-size * 0.05, size * 1.05, 90)],
            ctx.px(3.4), ctx.px(1.4), taper=0.8)
        ctx.paint(rule, PAL[spec.ink_color], spec.waterline)

    if spec.motif is not None:
        spec.motif(ctx)

    canvas.multiply_alpha(MAX_ALPHA)
    # Never bleed above the waterline — the sky owns everything up there.
    y = np.linspace(0.0, 1.0, size, dtype=np.float32)
    canvas.multiply_alpha(smoothstep(HORIZON - 0.035, HORIZON + 0.005, y)[:, None])
    return canvas


def all_keys() -> list[str]:
    return list(SEA_SPECS)
