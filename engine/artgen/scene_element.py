# SPDX-License-Identifier: MIT
"""Scene element layer (z-order 3 — between the sea and the ship).

Forty plates across five series: harbor, military, pirate, wizard, crystal.
Exactly one series can appear on an NFT (``traits.json`` makes the layer
single-select), so the series never mix by construction — but every element has
to share a frame with any of the sixteen ships, which drives the composition:

**Everything reads as distance.** These sit *behind* the vessel, so they are
drawn small, seated on or near the shared waterline, with thinner strokes and
lower contrast than the ship's linework. An element that competes with the ship
for weight stops being a setting and becomes clutter.

**The centre is surrendered.** ``clearance_mask`` attenuates alpha inside the
ellipse the ship's mass occupies, so structures pass *behind* the hull instead
of tangling with it at the edges. The wizard and crystal series, which are
meant to float around the vessel, carry a weaker clearance.

The waterline is ``SEA_HORIZON``, shared with the sea and ship_condition
layers; anything sitting on the water keys off it rather than guessing.
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
    rng_for,
    smoothstep,
    value_noise,
)

PAL = load_palette()

SEA_HORIZON = 0.58
"""Canvas waterline — shared with sea/ship_condition."""

SHIP_CORE = (0.50, 0.62, 0.34, 0.30)
"""(cx, cy, rx, ry) of the ship's mass, from the measured occupancy field."""

MAX_ALPHA = 0.88


def _c(*names: str) -> list[tuple[int, int, int]]:
    return [PAL[n] for n in names]


@dataclass(frozen=True)
class SceneSpec:
    key: str
    series: str
    colors: list[tuple[int, int, int]]
    ink_color: str = "deep_navy"
    line_alpha: float = 0.74
    clearance: float = 0.30
    """Alpha retained inside the ship's core; lower keeps the hull cleaner."""
    motif: Callable[["SceneCtx"], None] | None = None
    notes: str = ""
    extras: dict = dc_field(default_factory=dict)


@dataclass
class SceneCtx:
    spec: SceneSpec
    size: int
    rng: np.random.Generator
    canvas: Canvas

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

    @property
    def water(self) -> float:
        """Waterline in pixels."""
        return self.size * SEA_HORIZON

    def edge_x(self, side: int, inset: float) -> float:
        """x on the left (-1) or right (+1) margin, ``inset`` in from the edge."""
        return self.size * (inset if side < 0 else 1.0 - inset)


# ------------------------------------------------------------- shared marks


def _silhouette_ship(ctx: SceneCtx, mask: np.ndarray, cx: float, y: float,
                     length: float, *, masts: int = 2, sails: bool = False,
                     ghost: bool = False) -> None:
    """A distant vessel: hull wedge, masts, optional sails. Line only."""
    rng = ctx.rng
    h = length * 0.20
    hull = [(cx - length / 2, y), (cx + length / 2, y),
            (cx + length * 0.40, y + h), (cx - length * 0.44, y + h * 0.9)]
    w = ctx.px(5.0)
    if ghost:
        ink.polyline(mask, hull, w * 0.9, 0.85, closed=True)
    else:
        ink.fill_poly(mask, hull, 0.75)
        ink.polyline(mask, hull, w, 1.0, closed=True)
    for i in range(masts):
        mx = cx - length * 0.26 + length * 0.52 * (i / max(1, masts - 1))
        top = y - length * float(rng.uniform(0.34, 0.52))
        ink.calligraphic_stroke(mask, [(mx, y), (mx, top)], w, w * 0.5, taper=1.0)
        if sails:
            bulge = length * 0.13
            ink.calligraphic_stroke(
                mask, ink.catmull_rom([(mx, top + length * 0.06),
                                       (mx + bulge, (top + y) / 2),
                                       (mx, y - length * 0.04)]),
                w * 0.8, w * 0.5, taper=1.0)


def _piling_row(ctx: SceneCtx, mask: np.ndarray, x0: float, x1: float,
                y: float, n: int, *, height: float, broken: float = 0.0) -> None:
    """Posts standing in the water, some snapped short."""
    rng = ctx.rng
    tops: list[tuple[float, float]] = []
    for i in range(n):
        x = x0 + (x1 - x0) * i / max(1, n - 1)
        h = height * float(rng.uniform(0.7, 1.15))
        if rng.random() < broken:
            h *= float(rng.uniform(0.25, 0.6))
        lean = float(rng.uniform(-0.09, 0.09)) * h
        ink.calligraphic_stroke(mask, [(x, y + height * 0.22), (x + lean, y - h)],
                                ctx.px(11.0), ctx.px(8.0), taper=1.0)
        tops.append((x + lean, y - h))
    # Cross-bracing between neighbours: this is what separates a trestle from a
    # row of sticks. Without it the row reads as a picket fence.
    for a, b in zip(tops, tops[1:]):
        if rng.random() < 0.75:
            ink.polyline(mask, [(a[0], a[1] + (y - a[1]) * 0.55), b], ctx.px(4.0), 0.7)
        if rng.random() < 0.5:
            ink.polyline(mask, [a, (b[0], b[1] + (y - b[1]) * 0.55)], ctx.px(4.0), 0.6)


def _deck(ctx: SceneCtx, mask: np.ndarray, x0: float, x1: float, y: float,
          *, thickness: float, ragged: float = 0.0) -> None:
    rng = ctx.rng
    t = ctx.px(thickness)
    if ragged <= 0:
        ink.fill_poly(mask, [(x0, y), (x1, y), (x1, y + t), (x0, y + t)], 1.0)
        return
    pts_top, pts_bot = [], []
    n = 18
    for i in range(n):
        x = x0 + (x1 - x0) * i / (n - 1)
        d = ctx.px(float(rng.uniform(-ragged, ragged)))
        pts_top.append((x, y + d))
        pts_bot.append((x, y + t + d))
    ink.fill_poly(mask, pts_top + pts_bot[::-1], 1.0)


def _crane(ctx: SceneCtx, mask: np.ndarray, x: float, y: float, h: float,
           side: int) -> None:
    w = ctx.px(6.0)
    ink.calligraphic_stroke(mask, [(x, y), (x, y - h)], w, w * 0.8, taper=1.0)
    jib = h * 0.75
    ink.calligraphic_stroke(mask, [(x, y - h), (x + side * jib, y - h * 0.82)],
                            w * 0.8, w * 0.5, taper=1.0)
    ink.polyline(mask, [(x + side * jib, y - h * 0.82),
                        (x + side * jib, y - h * 0.36)], w * 0.5, 0.85)
    for t in np.linspace(0.1, 0.9, 6):
        ink.polyline(mask, [(x, y - h * t), (x, y - h * (t + 0.1))], w * 0.3, 0.5)


def _tower(ctx: SceneCtx, mask: np.ndarray, x: float, y: float, h: float,
           *, bands: int = 4) -> None:
    top_w, base_w = ctx.px(26), ctx.px(52)
    ink.fill_poly(mask, [(x - base_w, y), (x + base_w, y),
                         (x + top_w, y - h), (x - top_w, y - h)], 0.8)
    ink.polyline(mask, [(x - base_w, y), (x + top_w, y - h)], ctx.px(5.0), 1.0)
    ink.polyline(mask, [(x + base_w, y), (x - top_w, y - h)], 0.0, 0.0)
    ink.polyline(mask, [(x + base_w, y), (x + top_w, y - h)], ctx.px(5.0), 1.0)
    for i in range(bands):
        t = (i + 0.5) / bands
        w = base_w + (top_w - base_w) * t
        ink.polyline(mask, [(x - w, y - h * t), (x + w, y - h * t)], ctx.px(3.4), 0.8)
    # lantern room
    ink.polyline(mask, [(x - top_w * 1.5, y - h), (x + top_w * 1.5, y - h),
                        (x + top_w * 1.2, y - h * 1.14),
                        (x - top_w * 1.2, y - h * 1.14)],
                 ctx.px(5.0), 1.0, closed=True)


def _crystal_cluster(ctx: SceneCtx, mask: np.ndarray, facets: np.ndarray,
                     cx: float, y: float, scale: float, count: int = 5) -> None:
    """Shards rising out of the water — the crystal series' basic unit."""
    rng = ctx.rng
    for _ in range(count):
        x = cx + float(rng.uniform(-1.0, 1.0)) * scale * 0.9
        h = scale * float(rng.uniform(0.5, 1.5))
        w = h * float(rng.uniform(0.20, 0.36))
        tilt = float(rng.uniform(-0.30, 0.30))
        pts = [(0.0, -h), (w, -h * 0.45), (w * 0.7, 0.0), (-w * 0.7, 0.0),
               (-w, -h * 0.45)]
        rot = [(x + px_ * math.cos(tilt) - py * math.sin(tilt),
                y + px_ * math.sin(tilt) + py * math.cos(tilt)) for px_, py in pts]
        ink.fill_poly(mask, rot, 1.0)
        ink.polyline(facets, rot, ctx.px(4.0), 1.0, closed=True)
        ink.polyline(facets, [rot[0], rot[2]], ctx.px(2.6), 0.7)
        ink.polyline(facets, [rot[0], rot[3]], ctx.px(2.6), 0.7)


def _rune_ring(ctx: SceneCtx, mask: np.ndarray, cx: float, cy: float, r: float,
               *, glyphs: int = 12, rings: int = 2, squash: float = 0.42) -> None:
    """A circle of glyphs seen at an angle — the wizard series' basic unit."""
    rng = ctx.rng
    for k in range(rings):
        rr = r * (1.0 - k * 0.16)
        pts = [(cx + math.cos(a) * rr, cy + math.sin(a) * rr * squash)
               for a in np.linspace(0, 2 * math.pi, 200)]
        ink.calligraphic_stroke(mask, pts + [pts[0]], ctx.px(5.0 - k),
                                ctx.px(3.0), taper=0.6)
    for i in range(glyphs):
        a = i / glyphs * 2 * math.pi
        gx = cx + math.cos(a) * r * 0.86
        gy = cy + math.sin(a) * r * 0.86 * squash
        n = int(rng.integers(3, 6))
        size = ctx.px(float(rng.uniform(16, 30)))
        poly = [(gx + math.cos(t) * size, gy + math.sin(t) * size * 0.8)
                for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]
        ink.polyline(mask, poly, ctx.px(3.0), float(rng.uniform(0.55, 1.0)),
                     closed=True)


# ------------------------------------------------------------------ motifs


def motif_harbor(ctx: SceneCtx) -> None:
    """Pier structures on the waterline, at one or both margins."""
    s, rng = ctx.size, ctx.rng
    ex = ctx.spec.extras
    m = ctx.ink_mask()
    y = ctx.water
    for side in ex.get("sides", (-1, 1)):
        x_in = ctx.edge_x(side, 0.02)
        x_out = ctx.edge_x(side, ex.get("reach", 0.30))
        lo, hi = min(x_in, x_out), max(x_in, x_out)
        _piling_row(ctx, m, lo, hi, y, ex.get("pilings", 7),
                    height=s * ex.get("post_h", 0.135),
                    broken=ex.get("broken", 0.0))
        _deck(ctx, m, lo, hi, y - s * ex.get("post_h", 0.135) * 0.92,
              thickness=ex.get("deck", 24.0), ragged=ex.get("ragged", 0.0))
        for _ in range(ex.get("cranes", 0)):
            _crane(ctx, m, lo + (hi - lo) * float(rng.uniform(0.2, 0.8)),
                   y - s * ex.get("post_h", 0.135) * 0.9, s * 0.20, -side)
    for _ in range(ex.get("hulks", 0)):
        side = 1 if rng.random() < 0.5 else -1
        _silhouette_ship(ctx, m, ctx.edge_x(side, float(rng.uniform(0.10, 0.26))),
                         y - s * 0.008, s * float(rng.uniform(0.17, 0.25)),
                         masts=int(rng.integers(1, 3)), ghost=True)
    ctx.paint(m, PAL[ctx.spec.ink_color], ctx.spec.line_alpha)
    if ex.get("tower"):
        t = ctx.ink_mask()
        side = ex.get("tower_side", -1)
        _tower(ctx, t, ctx.edge_x(side, 0.14), y - s * 0.01, s * 0.34)
        ctx.paint(t, PAL[ctx.spec.ink_color], ctx.spec.line_alpha + 0.12)
        beam = ctx.ink_mask()
        bx, by = ctx.edge_x(side, 0.14), y - s * 0.29
        for spread in (0.035, 0.07):
            ink.fill_poly(beam, [(bx, by), (bx - side * s * 0.55, by - s * spread),
                                 (bx - side * s * 0.55, by + s * spread)], 1.0)
        ctx.paint(ctx.soft(beam, 34.0) * 0.55, PAL["pale_gold"], 0.42)


def motif_fleet(ctx: SceneCtx) -> None:
    """A line of distant hulls on the horizon."""
    s, rng = ctx.size, ctx.rng
    ex = ctx.spec.extras
    m = ctx.ink_mask()
    n = ex.get("ships", 5)
    for i in range(n):
        t = (i + 0.5) / n
        x = s * (0.06 + 0.88 * t) + float(rng.uniform(-0.03, 0.03)) * s
        depth = float(rng.uniform(0.6, 1.0))
        _silhouette_ship(ctx, m, x, ctx.water - s * float(rng.uniform(0.0, 0.02)),
                         s * ex.get("scale", 0.19) * depth,
                         masts=int(rng.integers(1, 4)),
                         sails=ex.get("sails", False), ghost=ex.get("ghost", False))
    alpha = ctx.spec.line_alpha * (0.95 if ex.get("ghost") else 1.0)
    ctx.paint(m, PAL[ctx.spec.ink_color], alpha)
    if ex.get("fog"):
        haze = value_noise(s, s, 4, rng)
        y = np.linspace(0.0, 1.0, s, dtype=np.float32)[:, None]
        band = np.exp(-((y - (SEA_HORIZON - 0.03)) / 0.075) ** 2)
        ctx.paint(band * (0.45 + 0.55 * haze) * 0.26, PAL["ash_gray"])


def motif_smoke(ctx: SceneCtx) -> None:
    """Artillery columns rising off the horizon."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    for _ in range(5):
        x = float(rng.uniform(0.08, 0.92)) * s
        ink.tendril(m, x, ctx.water, s * float(rng.uniform(0.22, 0.40)),
                    -math.pi / 2 + float(rng.uniform(-0.30, 0.30)), rng,
                    width=ctx.px(float(rng.uniform(6, 11))),
                    curl_radius=float(rng.uniform(0.10, 0.24)), sway=0.42)
    ctx.paint(m, PAL["slate_gray"], 0.52)
    ctx.paint(ctx.soft(m, 42.0) * 0.9, PAL["ash_gray"], 0.34)
    flash = ctx.ink_mask()
    for _ in range(3):
        x = float(rng.uniform(0.12, 0.88)) * s
        ink.star_field(flash, rng, 1, y_range=(SEA_HORIZON - 0.01, SEA_HORIZON),
                       size_range=(ctx.px(20), ctx.px(34)), sparkle_frac=1.0)
    ctx.paint(ctx.soft(flash, 20.0), PAL["ember_orange"], 0.55)


def motif_searchlights(ctx: SceneCtx) -> None:
    """Beams sweeping up from below the horizon."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    edges = ctx.ink_mask()
    for _ in range(5):
        x = float(rng.uniform(0.05, 0.95)) * s
        ang = -math.pi / 2 + float(rng.uniform(-0.55, 0.55))
        length = s * float(rng.uniform(0.42, 0.66))
        w0, w1 = ctx.px(20), ctx.px(90)
        tip = (x + math.cos(ang) * length, ctx.water + math.sin(ang) * length)
        perp = ang + math.pi / 2
        ink.fill_poly(m, [
            (x - math.cos(perp) * w0, ctx.water - math.sin(perp) * w0),
            (x + math.cos(perp) * w0, ctx.water + math.sin(perp) * w0),
            (tip[0] + math.cos(perp) * w1, tip[1] + math.sin(perp) * w1),
            (tip[0] - math.cos(perp) * w1, tip[1] - math.sin(perp) * w1)], 1.0)
        # A drawn edge: a pure blur reads as a smudge, not a beam.
        ink.polyline(edges, [
            (x - math.cos(perp) * w0, ctx.water - math.sin(perp) * w0),
            (tip[0] - math.cos(perp) * w1, tip[1] - math.sin(perp) * w1)],
            ctx.px(4.0), 0.9)
        ink.polyline(edges, [
            (x + math.cos(perp) * w0, ctx.water + math.sin(perp) * w0),
            (tip[0] + math.cos(perp) * w1, tip[1] + math.sin(perp) * w1)],
            ctx.px(4.0), 0.9)
    ctx.paint(ctx.soft(m, 34.0) * 0.95, PAL["pale_blue"], 0.60)
    ctx.paint(ctx.soft(m, 10.0) * 0.6, PAL["bone_white"], 0.42)
    ctx.paint(ctx.soft(edges, 5.0), PAL["bone_white"], 0.55)


def motif_flags(ctx: SceneCtx) -> None:
    """A string of signal flags strung across the upper frame."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    fills = ctx.ink_mask()
    y0 = s * float(rng.uniform(0.16, 0.24))
    sag = s * 0.10
    pts = ink.catmull_rom([(-s * 0.05, y0), (s * 0.5, y0 + sag), (s * 1.05, y0 * 0.9)],
                          samples_per_span=24)
    ink.calligraphic_stroke(m, pts, ctx.px(4.0), ctx.px(3.0), taper=0.8)
    for i in range(2, len(pts) - 2, 3):
        x, y = pts[i]
        w = ctx.px(float(rng.uniform(26, 40)))
        h = ctx.px(float(rng.uniform(46, 74)))
        poly = [(x - w, y), (x + w, y), (x + w * 0.5, y + h)]
        ink.fill_poly(fills, poly, float(rng.uniform(0.25, 0.9)))
        ink.polyline(m, poly, ctx.px(3.0), 1.0, closed=True)
    ctx.paint(fills * 0.7, PAL["crimson"], 0.55)
    ctx.paint(m, PAL[ctx.spec.ink_color], ctx.spec.line_alpha)


def motif_aircraft(ctx: SceneCtx) -> None:
    """A helicopter or a parachute drop in the upper frame."""
    s, rng = ctx.size, ctx.rng
    ex = ctx.spec.extras
    m = ctx.ink_mask()
    if ex.get("chutes"):
        for _ in range(4):
            x = float(rng.uniform(0.10, 0.90)) * s
            y = float(rng.uniform(0.14, 0.36)) * s
            r = ctx.px(float(rng.uniform(52, 92)))
            dome = [(x + math.cos(a) * r, y - math.sin(a) * r * 0.72)
                    for a in np.linspace(0, math.pi, 26)]
            ink.calligraphic_stroke(m, dome, ctx.px(5.0), ctx.px(3.5), taper=0.8)
            for t in (-1.0, -0.4, 0.4, 1.0):
                ink.polyline(m, [(x + r * t, y), (x, y + r * 1.25)], ctx.px(2.6), 0.8)
            ink.polyline(m, [(x - r * 0.22, y + r * 1.25), (x + r * 0.22, y + r * 1.25),
                             (x + r * 0.22, y + r * 1.6), (x - r * 0.22, y + r * 1.6)],
                         ctx.px(4.0), 1.0, closed=True)
    else:
        x, y = s * float(rng.uniform(0.24, 0.72)), s * float(rng.uniform(0.16, 0.26))
        body = ctx.px(96)
        ink.fill_poly(m, [(x - body, y), (x + body * 0.5, y - body * 0.42),
                          (x + body, y - body * 0.1), (x + body * 0.7, y + body * 0.36),
                          (x - body * 0.8, y + body * 0.3)], 0.7)
        ink.polyline(m, [(x - body, y), (x + body * 0.5, y - body * 0.42),
                         (x + body, y - body * 0.1), (x + body * 0.7, y + body * 0.36),
                         (x - body * 0.8, y + body * 0.3)], ctx.px(5.0), 1.0, closed=True)
        ink.calligraphic_stroke(m, [(x - body * 1.0, y - body * 0.1),
                                    (x - body * 2.6, y - body * 0.2)],
                                ctx.px(9.0), ctx.px(5.0), taper=1.0)
        for d in (-1, 1):
            ink.calligraphic_stroke(m, [(x + body * 0.1, y - body * 0.55),
                                        (x + d * body * 2.3, y - body * 0.72)],
                                    ctx.px(5.0), ctx.px(2.0), taper=1.3)
        ink.polyline(m, [(x + body * 0.1, y - body * 0.42),
                         (x + body * 0.1, y - body * 0.58)], ctx.px(5.0), 1.0)
    ctx.paint(m, PAL[ctx.spec.ink_color], ctx.spec.line_alpha)


def motif_flag(ctx: SceneCtx) -> None:
    """A single tall standard — the pirate colours."""
    s = ctx.size
    m = ctx.ink_mask()
    fill = ctx.ink_mask()
    side = ctx.spec.extras.get("side", 1)
    x = ctx.edge_x(side, 0.17)
    base = ctx.water + s * 0.01
    top = base - s * 0.40
    ink.calligraphic_stroke(m, [(x, base), (x, top)], ctx.px(10.0), ctx.px(6.0),
                            taper=1.0)
    w = s * 0.17 * -side
    wave = s * 0.022
    upper = [(x + w * t, top + math.sin(t * 3.4) * wave)
             for t in np.linspace(0, 1, 22)]
    lower = [(x + w * t, top + s * 0.115 + math.sin(t * 3.4 + 0.7) * wave)
             for t in np.linspace(0, 1, 22)]
    ink.fill_poly(fill, upper + lower[::-1], 1.0)
    ink.polyline(m, upper + lower[::-1], ctx.px(4.0), 1.0, closed=True)
    # skull
    sx, sy = x + w * 0.45, top + s * 0.055
    r = ctx.px(28)
    ink.polyline(m, [(sx + math.cos(a) * r, sy + math.sin(a) * r * 1.1)
                     for a in np.linspace(0, 2 * math.pi, 24)], ctx.px(4.0), 1.0,
                 closed=True)
    for d in (-1, 1):
        ink.polyline(m, [(sx + d * r * 0.4 - r * 0.18, sy - r * 0.1),
                         (sx + d * r * 0.4 + r * 0.18, sy + r * 0.2)], ctx.px(6.0), 1.0)
    for d in (-1, 1):
        ink.polyline(m, [(sx - r * 1.5, sy + r * 1.5 * d),
                         (sx + r * 1.5, sy - r * 1.5 * d)], ctx.px(5.0), 0.9)
    ctx.paint(fill * 0.85, PAL["ink_black"], 0.72)
    ctx.paint(m, PAL[ctx.spec.ink_color], ctx.spec.line_alpha + 0.15)


def motif_island(ctx: SceneCtx) -> None:
    """A land mass on the horizon with palms or a cave mouth."""
    s, rng = ctx.size, ctx.rng
    ex = ctx.spec.extras
    m = ctx.ink_mask()
    fill = ctx.ink_mask()
    side = ex.get("side", -1)
    cx = ctx.edge_x(side, float(rng.uniform(0.16, 0.26)))
    w = s * float(rng.uniform(0.26, 0.38))
    h = s * float(rng.uniform(0.15, 0.24))
    y = ctx.water
    ridge = [(cx - w, y)]
    for t in np.linspace(0.08, 0.92, 9):
        ridge.append((cx - w + 2 * w * t,
                      y - h * (math.sin(math.pi * t) ** 0.8)
                      * float(rng.uniform(0.75, 1.15))))
    ridge.append((cx + w, y))
    ink.fill_poly(fill, ridge + [(cx + w, y + s * 0.03), (cx - w, y + s * 0.03)], 1.0)
    ink.calligraphic_stroke(m, ridge, ctx.px(5.0), ctx.px(3.0), taper=0.8)
    if ex.get("palms"):
        for _ in range(3):
            px_ = cx + float(rng.uniform(-0.6, 0.6)) * w
            top = y - h * float(rng.uniform(0.8, 1.3)) - s * 0.05
            ink.calligraphic_stroke(m, ink.catmull_rom(
                [(px_, y - h * 0.3), (px_ + s * 0.012, (y + top) / 2), (px_, top)]),
                ctx.px(6.0), ctx.px(3.0), taper=1.0)
            for a in np.linspace(-2.4, -0.7, 5):
                ink.calligraphic_stroke(
                    m, [(px_, top), (px_ + math.cos(a) * s * 0.05,
                                     top + math.sin(a) * s * 0.03)],
                    ctx.px(4.0), ctx.px(1.2), taper=1.4)
    if ex.get("cave"):
        r = s * 0.045
        ink.fill_poly(m, [(cx + math.cos(a) * r, y - abs(math.sin(a)) * r * 1.4)
                          for a in np.linspace(0, 2 * math.pi, 30)], 0.95)
    ctx.paint(fill * 0.35, PAL[ctx.spec.ink_color], 0.55)
    ctx.paint(m, PAL[ctx.spec.ink_color], ctx.spec.line_alpha + 0.12)


def motif_skeletons(ctx: SceneCtx) -> None:
    """Bones wading in the shallows, drawn as silhouettes.

    Outlined skulls do not survive background scale — two dots in a circle read
    as a smiley, not a skull. Solid shapes do: a filled cranium with a knocked-
    out socket and jaw, a blocky ribcage, and the legs simply lost under the
    waterline. Read is bought with contrast here, not detail.
    """
    s, rng = ctx.size, ctx.rng
    solid = ctx.ink_mask()
    cut = ctx.ink_mask()
    for slot in (-1, 1):
        for j in range(2):
            x = ctx.edge_x(slot, float(rng.uniform(0.09, 0.24))) + j * s * 0.062 * slot
            y = ctx.water + s * float(rng.uniform(0.0, 0.025))
            h = s * float(rng.uniform(0.17, 0.24))
            sx, sy = x, y - h
            r = h * 0.20
            # cranium + jaw as one mass
            ink.fill_poly(solid, [(sx + math.cos(a) * r, sy + math.sin(a) * r * 1.05)
                                  for a in np.linspace(0, 2 * math.pi, 28)], 1.0)
            ink.fill_poly(solid, [(sx - r * 0.62, sy + r * 0.5), (sx + r * 0.62, sy + r * 0.5),
                                  (sx + r * 0.42, sy + r * 1.32),
                                  (sx - r * 0.42, sy + r * 1.32)], 1.0)
            for d in (-1, 1):   # sockets knocked back out
                ink.fill_poly(cut, [(sx + d * r * 0.44 + math.cos(a) * r * 0.32,
                                     sy - r * 0.08 + math.sin(a) * r * 0.38)
                                    for a in np.linspace(0, 2 * math.pi, 18)], 1.0)
            for k in range(3):  # teeth
                tx = sx - r * 0.34 + r * 0.34 * k
                ink.polyline(cut, [(tx, sy + r * 0.62), (tx, sy + r * 1.24)],
                             ctx.px(6.0), 1.0)
            # ribcage: solid bars, tapering
            for i in range(4):
                t = i / 3
                ry = sy + r * 1.7 + (y - h * 0.15 - sy - r * 1.7) * t
                half = h * (0.19 - 0.07 * t)
                ink.calligraphic_stroke(
                    solid, ink.catmull_rom([(sx - half, ry - h * 0.025), (sx, ry),
                                            (sx + half, ry - h * 0.025)]),
                    ctx.px(15.0), ctx.px(9.0), taper=0.8)
            ink.calligraphic_stroke(solid, [(sx, sy + r * 1.3), (sx, y - h * 0.10)],
                                    ctx.px(13.0), ctx.px(10.0), taper=1.0)
            for d in (-1, 1):
                ink.calligraphic_stroke(
                    solid, ink.catmull_rom([(sx + d * r * 0.5, sy + r * 1.9),
                                            (sx + d * h * 0.27, y - h * 0.40),
                                            (sx + d * h * 0.20, y - h * 0.04)]),
                    ctx.px(12.0), ctx.px(6.0), taper=1.1)
    ctx.paint(solid, PAL[ctx.spec.ink_color], min(1.0, ctx.spec.line_alpha + 0.20))
    ctx.paint(cut, PAL["bone_white"], 0.92)


def motif_crows_nest(ctx: SceneCtx) -> None:
    """A lone mast top with a barrel, rising out of the water."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    side = ctx.spec.extras.get("side", 1)
    x = ctx.edge_x(side, float(rng.uniform(0.16, 0.24)))
    base = ctx.water + s * 0.02
    top = base - s * 0.30
    ink.calligraphic_stroke(m, [(x, base), (x, top)], ctx.px(13.0), ctx.px(8.0),
                            taper=1.0)
    bw, bh = ctx.px(64), ctx.px(76)
    ink.polyline(m, [(x - bw, top + bh * 0.2), (x + bw, top + bh * 0.2),
                     (x + bw * 0.78, top - bh * 0.8), (x - bw * 0.78, top - bh * 0.8)],
                 ctx.px(5.0), 1.0, closed=True)
    for t in (0.25, 0.6):
        yy = top + bh * 0.2 - (bh * 1.0) * t
        ink.polyline(m, [(x - bw * 0.95, yy), (x + bw * 0.95, yy)], ctx.px(3.4), 0.85)
    ink.calligraphic_stroke(m, [(x, top - bh * 0.8), (x, top - s * 0.06)],
                            ctx.px(6.0), ctx.px(3.0), taper=1.0)
    for d in (-1, 1):
        ink.polyline(m, [(x, top - s * 0.04),
                         (x + d * s * 0.10, base - s * 0.06)], ctx.px(3.0), 0.7)
    ctx.paint(m, PAL[ctx.spec.ink_color], ctx.spec.line_alpha + 0.12)


def motif_wizard(ctx: SceneCtx) -> None:
    """Floating geometry: rune rings, lanterns, sigils, a scroll."""
    s, rng = ctx.size, ctx.rng
    ex = ctx.spec.extras
    glow_col = PAL[ex.get("glow", "amethyst")]
    m = ctx.ink_mask()

    for _ in range(ex.get("rings", 1)):
        side = 1 if rng.random() < 0.5 else -1
        cx = ctx.edge_x(side, float(rng.uniform(0.16, 0.30)))
        cy = s * float(rng.uniform(0.30, 0.52))
        _rune_ring(ctx, m, cx, cy, s * float(rng.uniform(0.15, 0.23)),
                   glyphs=int(rng.integers(8, 15)),
                   rings=ex.get("ring_lines", 2),
                   squash=ex.get("squash", 0.42))

    for _ in range(ex.get("lanterns", 0)):
        x = float(rng.uniform(0.05, 0.95)) * s
        y = float(rng.uniform(0.20, 0.52)) * s
        r = ctx.px(float(rng.uniform(26, 46)))
        ink.polyline(m, [(x - r, y - r), (x + r, y - r), (x + r * 0.8, y + r),
                         (x - r * 0.8, y + r)], ctx.px(4.0), 1.0, closed=True)
        ink.polyline(m, [(x, y - r), (x, y - r * 1.8)], ctx.px(3.0), 0.8)
        ctx.paint(ctx.soft(_dot(ctx, x, y, r * 0.55), 26.0) * 1.3, glow_col, 0.55)

    for _ in range(ex.get("runes", 0)):
        x = float(rng.uniform(0.04, 0.96)) * s
        y = float(rng.uniform(0.14, 0.54)) * s
        size = ctx.px(float(rng.uniform(26, 62)))
        n = int(rng.integers(3, 7))
        poly = [(x + math.cos(a) * size, y + math.sin(a) * size)
                for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
        ink.polyline(m, poly, ctx.px(4.0), float(rng.uniform(0.5, 1.0)), closed=True)
        for j in range(0, n, 2):
            ink.polyline(m, [poly[j], poly[(j + 2) % n]], ctx.px(2.6), 0.6)

    if ex.get("scroll"):
        _scroll(ctx, m)

    ctx.paint(m, PAL[ctx.spec.ink_color], ctx.spec.line_alpha + 0.16)
    ctx.paint(ctx.soft(m, 30.0) * 1.1, glow_col, 0.42)


def _dot(ctx: SceneCtx, x: float, y: float, r: float) -> np.ndarray:
    d = ctx.ink_mask()
    ink.fill_poly(d, [(x + math.cos(a) * r, y + math.sin(a) * r)
                      for a in np.linspace(0, 2 * math.pi, 24)], 1.0)
    return d


def _scroll(ctx: SceneCtx, m: np.ndarray) -> None:
    """An unrolled offer file — the Chia-native meme trait."""
    s, rng = ctx.size, ctx.rng
    cx = s * float(rng.uniform(0.24, 0.40))
    cy = s * float(rng.uniform(0.28, 0.40))
    w, h = s * 0.16, s * 0.20
    ink.polyline(m, [(cx - w, cy - h), (cx + w, cy - h * 0.92),
                     (cx + w, cy + h), (cx - w, cy + h * 0.94)],
                 ctx.px(6.0), 1.0, closed=True)
    for d in (-1, 1):
        ink.calligraphic_stroke(
            m, ink.spiral(cx + d * w, cy - h * d * 0.02, ctx.px(34), ctx.px(6),
                          1.4, samples=80), ctx.px(6.0), ctx.px(3.0), taper=1.0)
    for i in range(7):
        y = cy - h * 0.7 + h * 1.4 * (i / 6)
        ink.polyline(m, [(cx - w * 0.72, y),
                         (cx + w * float(rng.uniform(0.3, 0.72)), y)],
                     ctx.px(3.4), 0.7)


def motif_crystal(ctx: SceneCtx) -> None:
    """Crystal formations: clusters on the water, a reef, or a hanging moon."""
    s, rng = ctx.size, ctx.rng
    ex = ctx.spec.extras
    body = ctx.ink_mask()
    facets = ctx.ink_mask()

    if ex.get("moon"):
        cx, cy = s * float(rng.uniform(0.62, 0.76)), s * float(rng.uniform(0.16, 0.24))
        r = s * 0.115
        n = 8
        poly = [(cx + math.cos(a) * r, cy + math.sin(a) * r)
                for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
        ink.fill_poly(body, poly, 1.0)
        ink.polyline(facets, poly, ctx.px(6.0), 1.0, closed=True)
        for i in range(n):
            ink.polyline(facets, [poly[i], (cx, cy)], ctx.px(3.0), 0.6)
        ctx.paint(ctx.soft(body, 60.0) * 1.2, ctx.spec.colors[0], 0.42)

    for _ in range(ex.get("clusters", 2)):
        side = 1 if rng.random() < 0.5 else -1
        cx = ctx.edge_x(side, float(rng.uniform(0.10, 0.28)))
        _crystal_cluster(ctx, body, facets, cx, ctx.water + s * 0.01,
                         s * float(rng.uniform(0.15, 0.27)),
                         count=int(rng.integers(4, 8)))

    if ex.get("reef"):
        for _ in range(9):
            x = float(rng.uniform(0.02, 0.98)) * s
            _crystal_cluster(ctx, body, facets, x,
                             ctx.water + s * float(rng.uniform(0.0, 0.06)),
                             s * float(rng.uniform(0.06, 0.13)), count=3)

    ctx.paint(body * ex.get("fill", 0.32), ctx.spec.colors[0], 0.62)
    ctx.paint(facets, PAL[ctx.spec.ink_color], min(1.0, ctx.spec.line_alpha + 0.24))
    ctx.paint(ctx.soft(facets, 26.0) * 1.0, ctx.spec.colors[-1], 0.36)
    if ex.get("shatter"):
        sh = ctx.ink_mask()
        for _ in range(40):
            x = float(rng.uniform(0.02, 0.98)) * s
            y = float(rng.uniform(0.18, 0.62)) * s
            r = ctx.px(float(rng.uniform(10, 40)))
            a = float(rng.uniform(0, math.pi))
            ink.polyline(sh, [(x, y), (x + math.cos(a) * r, y + math.sin(a) * r)],
                         ctx.px(3.0), float(rng.uniform(0.4, 1.0)))
        ctx.paint(sh, PAL[ctx.spec.ink_color], 0.6)


# -------------------------------------------------------------------- specs

def _harbor(key, ink_color="deep_navy", alpha=0.74, **extras) -> SceneSpec:
    return SceneSpec(key, "harbor", _c("slate_gray", "deep_navy"),
                     ink_color=ink_color, line_alpha=alpha,
                     motif=motif_harbor, extras=extras)


SCENE_SPECS: dict[str, SceneSpec] = {
    # ---------------------------------------------------------------- harbor
    "harbor_abandoned_harbor": _harbor(
        "harbor_abandoned_harbor", pilings=8, broken=0.55, ragged=9.0, hulks=1),
    "harbor_broken_pier": _harbor(
        "harbor_broken_pier", sides=(-1,), reach=0.34, pilings=9, broken=0.7,
        ragged=13.0),
    "harbor_storm_harbor": _harbor(
        "harbor_storm_harbor", pilings=9, broken=0.35, ragged=7.0, cranes=1,
        ink_color="deep_ink", alpha=0.68),
    "harbor_ship_graveyard": _harbor(
        "harbor_ship_graveyard", sides=(-1, 1), pilings=4, broken=0.8, hulks=3,
        ragged=11.0),
    "harbor_dry_dock": _harbor(
        "harbor_dry_dock", sides=(1,), reach=0.36, pilings=8, deck=24.0, cranes=2),
    "harbor_lighthouse": _harbor(
        "harbor_lighthouse", sides=(-1,), reach=0.24, pilings=6, tower=True,
        tower_side=-1),
    "harbor_military_port": _harbor(
        "harbor_military_port", pilings=7, deck=22.0, cranes=2, hulks=2,
        ink_color="shadow_navy"),
    "harbor_pirate_cove": _harbor(
        "harbor_pirate_cove", sides=(1,), reach=0.30, pilings=6, broken=0.4,
        hulks=2, ragged=10.0, ink_color="maroon"),
    "harbor_wizard_harbor": _harbor(
        "harbor_wizard_harbor", pilings=7, cranes=1, ink_color="deep_violet",
        alpha=0.66),
    # -------------------------------------------------------------- military
    "military_convoy_silhouettes": SceneSpec(
        "military_convoy_silhouettes", "military", _c("slate_gray", "deep_navy"),
        ink_color="shadow_navy", motif=motif_fleet,
        extras={"ships": 6, "scale": 0.17}),
    "military_artillery_smoke": SceneSpec(
        "military_artillery_smoke", "military", _c("slate_gray", "ash_gray"),
        ink_color="slate_gray", motif=motif_smoke),
    "military_searchlights": SceneSpec(
        "military_searchlights", "military", _c("pale_blue", "steel_blue"),
        ink_color="steel_blue", clearance=0.55, motif=motif_searchlights),
    "military_signal_flags": SceneSpec(
        "military_signal_flags", "military", _c("crimson", "sand"),
        ink_color="deep_navy", clearance=0.55, motif=motif_flags),
    "military_cargo_drop": SceneSpec(
        "military_cargo_drop", "military", _c("bronze", "slate_gray"),
        ink_color="deep_ink", clearance=0.5, motif=motif_aircraft,
        extras={"chutes": True}),
    "military_helicopter": SceneSpec(
        "military_helicopter", "military", _c("slate_gray", "deep_ink"),
        ink_color="deep_ink", clearance=0.5, motif=motif_aircraft),
    # ---------------------------------------------------------------- pirate
    "pirate_black_flag": SceneSpec(
        "pirate_black_flag", "pirate", _c("ink_black", "maroon"),
        ink_color="ink_black", clearance=0.45, motif=motif_flag),
    "pirate_fog_fleet": SceneSpec(
        "pirate_fog_fleet", "pirate", _c("ash_gray", "slate_gray"),
        ink_color="slate_gray", motif=motif_fleet,
        extras={"ships": 5, "scale": 0.21, "sails": True, "fog": True}),
    "pirate_crows_nest": SceneSpec(
        "pirate_crows_nest", "pirate", _c("bronze", "deep_ink"),
        ink_color="deep_ink", motif=motif_crows_nest),
    "pirate_hidden_cove": SceneSpec(
        "pirate_hidden_cove", "pirate", _c("deep_teal", "deep_ink"),
        ink_color="deep_teal", motif=motif_island, extras={"cave": True, "side": -1}),
    "pirate_treasure_island": SceneSpec(
        "pirate_treasure_island", "pirate", _c("sand", "teal_green"),
        ink_color="bronze", motif=motif_island, extras={"palms": True, "side": 1}),
    "pirate_ghost_fleet": SceneSpec(
        "pirate_ghost_fleet", "pirate", _c("pale_blue", "ash_gray"),
        ink_color="navy", line_alpha=0.88, motif=motif_fleet,
        extras={"ships": 6, "scale": 0.21, "sails": True, "ghost": True, "fog": True}),
    "pirate_skeleton_crew": SceneSpec(
        "pirate_skeleton_crew", "pirate", _c("bone_white", "slate_gray"),
        ink_color="deep_ink", motif=motif_skeletons),
    # ---------------------------------------------------------------- wizard
    "wizard_green_magic": SceneSpec(
        "wizard_green_magic", "wizard", _c("bright_green", "chia_green"),
        ink_color="teal_green", clearance=0.5, motif=motif_wizard,
        extras={"glow": "bright_green", "rings": 1, "runes": 5}),
    "wizard_purple_magic": SceneSpec(
        "wizard_purple_magic", "wizard", _c("amethyst", "violet"),
        ink_color="deep_violet", clearance=0.5, motif=motif_wizard,
        extras={"glow": "amethyst", "rings": 1, "runes": 5}),
    "wizard_magic_lanterns": SceneSpec(
        "wizard_magic_lanterns", "wizard", _c("pale_gold", "amber"),
        ink_color="bronze", clearance=0.55, motif=motif_wizard,
        extras={"glow": "pale_gold", "rings": 0, "lanterns": 6}),
    "wizard_spell_circle": SceneSpec(
        "wizard_spell_circle", "wizard", _c("lavender", "amethyst"),
        ink_color="violet", clearance=0.45, motif=motif_wizard,
        extras={"glow": "lavender", "rings": 2, "ring_lines": 3, "runes": 3}),
    "wizard_floating_runes": SceneSpec(
        "wizard_floating_runes", "wizard", _c("amethyst", "lavender"),
        ink_color="deep_violet", clearance=0.55, motif=motif_wizard,
        extras={"glow": "lavender", "rings": 0, "runes": 16}),
    "wizard_summoning_circle": SceneSpec(
        "wizard_summoning_circle", "wizard", _c("crimson", "amethyst"),
        ink_color="maroon", clearance=0.4, motif=motif_wizard,
        extras={"glow": "crimson", "rings": 1, "ring_lines": 4, "squash": 0.30,
                "runes": 6}),
    "wizard_blockchain_sigils": SceneSpec(
        "wizard_blockchain_sigils", "wizard", _c("chia_green", "bright_green"),
        ink_color="deep_teal", clearance=0.5, motif=motif_wizard,
        extras={"glow": "chia_green", "rings": 2, "ring_lines": 2, "runes": 10},
        notes="legendary — Chia-coded"),
    "wizard_offer_file_scroll": SceneSpec(
        "wizard_offer_file_scroll", "wizard", _c("sand", "chia_green"),
        ink_color="bronze", clearance=0.5, motif=motif_wizard,
        extras={"glow": "chia_green", "rings": 0, "runes": 3, "scroll": True},
        notes="legendary — Chia-native meme trait"),
    # --------------------------------------------------------------- crystal
    "crystal_emerald_horizon": SceneSpec(
        "crystal_emerald_horizon", "crystal", _c("bright_green", "deep_teal"),
        ink_color="deep_teal", motif=motif_crystal, extras={"clusters": 3}),
    "crystal_crystal_reef": SceneSpec(
        "crystal_crystal_reef", "crystal", _c("pale_blue", "steel_blue"),
        ink_color="navy", motif=motif_crystal, extras={"clusters": 1, "reef": True}),
    "crystal_crystal_moon": SceneSpec(
        "crystal_crystal_moon", "crystal", _c("lavender", "pale_blue"),
        ink_color="deep_violet", clearance=0.5, motif=motif_crystal,
        extras={"moon": True, "clusters": 1}),
    "crystal_fractured": SceneSpec(
        "crystal_fractured", "crystal", _c("ash_gray", "slate_gray"),
        ink_color="deep_ink", motif=motif_crystal,
        extras={"clusters": 2, "shatter": True}),
    "crystal_black": SceneSpec(
        "crystal_black", "crystal", _c("shadow_navy", "ink_black"),
        ink_color="ink_black", motif=motif_crystal,
        extras={"clusters": 3, "fill": 0.52}),
    "crystal_ruby": SceneSpec(
        "crystal_ruby", "crystal", _c("crimson", "maroon"),
        ink_color="maroon", motif=motif_crystal, extras={"clusters": 3, "fill": 0.44}),
    "crystal_sapphire": SceneSpec(
        "crystal_sapphire", "crystal", _c("sea_blue", "abyss_navy"),
        ink_color="abyss_navy", motif=motif_crystal,
        extras={"clusters": 3, "fill": 0.44}),
    "crystal_corrupted": SceneSpec(
        "crystal_corrupted", "crystal", _c("amethyst", "deep_violet"),
        ink_color="ink_black", motif=motif_crystal,
        extras={"clusters": 3, "shatter": True, "fill": 0.40}),
    "crystal_void": SceneSpec(
        "crystal_void", "crystal", _c("ink_black", "deep_ink"),
        ink_color="ink_black", clearance=0.5, motif=motif_crystal,
        extras={"moon": True, "clusters": 2, "fill": 0.62}),
    "crystal_chia_crystal": SceneSpec(
        "crystal_chia_crystal", "crystal", _c("chia_green", "bright_green"),
        ink_color="deep_teal", motif=motif_crystal,
        extras={"clusters": 3, "reef": True, "fill": 0.40},
        notes="mythic — the top of the ladder"),
}


# ------------------------------------------------------------------ render


def clearance_mask(size: int, keep: float) -> np.ndarray:
    """Attenuate alpha where the ship's mass sits, so elements pass behind it."""
    cx, cy, rx, ry = SHIP_CORE
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.hypot((xs - cx * size) / (rx * size), (ys - cy * size) / (ry * size))
    return (keep + (1.0 - keep) * smoothstep(0.62, 1.20, d)).astype(np.float32)


def render(trait_key: str, size: int = 2048) -> Canvas:
    """Render one scene element. Deterministic in ``trait_key``."""
    spec = SCENE_SPECS[trait_key]
    rng = rng_for(f"scene_element/{trait_key}/v1")
    canvas = Canvas(size)
    ctx = SceneCtx(spec=spec, size=size, rng=rng, canvas=canvas)
    if spec.motif is not None:
        spec.motif(ctx)
    canvas.multiply_alpha(clearance_mask(size, spec.clearance))
    canvas.multiply_alpha(MAX_ALPHA)
    return canvas


def all_keys() -> list[str]:
    return list(SCENE_SPECS)


def series_of(key: str) -> str:
    return SCENE_SPECS[key].series
