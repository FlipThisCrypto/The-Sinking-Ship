# SPDX-License-Identifier: MIT
"""Ship condition overlays (z-order 5 — sits directly on ship_class).

The hard problem in this layer: eleven conditions must read correctly over
*sixteen structurally unrelated* ship illustrations — a raft, a submarine, an
aircraft carrier — which share no hull line, mast position or deck height. The
trait contract is one sprite per condition, so an overlay cannot know which
ship is underneath it. Drawing a fixed hull-shaped decal is exactly how you get
a mess pasted on a mess.

Three devices avoid that:

**Water is ship-agnostic.** Half-sunk, flooded, fully-underwater and listing are
drawn as *waterline* events, not hull events — a rising, tilting or engulfing
surface that occludes whatever is beneath it. Water at a given height looks
right over any hull, and the ship reads through the surface at reduced alpha
instead of being blotted out.

**Damage follows measured occupancy.** ``ship_occupancy()`` measures where ink
actually falls across all sixteen ship plates. Flames, rifts, scaffolding and
salvage rigging are placed by sampling that field, so marks land on ship
structure for most classes instead of hanging in open water.

**The ghost echo is derived, not drawn.** The spectral double is the occupancy
silhouette itself, so it approximately traces whatever hull is underneath.

Coordinates: this layer has **no** ``layer_transforms`` entry, because water
must reach the frame edges and a transform would confine it to the ship's 0.8
box — which renders as a hard rectangle mid-frame. Instead the renderer reads
``ship_class``'s transform from config and maps ship-plate points into canvas
space itself (``ship_to_canvas``), so damage still lands on the hull while
water spans the picture.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field as dc_field
from functools import lru_cache
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from PIL import Image

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
ROOT = Path(__file__).resolve().parent.parent.parent
SPRITES = ROOT / "sprites"
CONFIG = ROOT / "config"

SEA_HORIZON = 0.58
"""Canvas y where the sea layer's waterline sits — this layer must agree."""

HULL_BAND = (0.42, 0.80)
"""Vertical extent of the hull mass in *ship-plate* space (measured occupancy)."""

MAX_ALPHA = 0.92


@lru_cache(maxsize=1)
def ship_placement() -> tuple[float, float, float]:
    """``(scale, anchor_x, anchor_y)`` ``render_engine`` composites ship_class with.

    Read from config rather than hardcoded so the two cannot drift apart. This
    layer has *no* transform of its own — water has to reach the frame edges,
    and a transform would confine it to the ship's box and render it as a
    rectangle mid-frame — so it maps ship coordinates into canvas space here.
    """
    doc = json.loads(
        (CONFIG / "render.json").read_text(encoding="utf-8")
    )
    tf = doc["profiles"]["illustration"]["layer_transforms"]["ship_class"]
    return (float(tf["scale"]), float(tf.get("anchor_x", 0.5)),
            float(tf.get("anchor_y", 1.0)))


def ship_to_canvas(u: float, v: float) -> tuple[float, float]:
    """Normalised ship-plate point -> normalised canvas point.

    Mirrors ``render_engine._place`` exactly, including ``anchor_x``: the ship
    is anchored to one side of the frame, so a mark placed as if it were
    centred lands well off the hull.
    """
    scale, anchor_x, anchor_y = ship_placement()
    return (anchor_x * (1.0 - scale) + u * scale,
            anchor_y * (1.0 - scale) + v * scale)


def canvas_waterline_in_ship_space() -> float:
    """Where the composite sea crosses the ship, in the ship's own coordinates."""
    scale, _, anchor_y = ship_placement()
    return (SEA_HORIZON - anchor_y * (1.0 - scale)) / scale


def _c(*names: str) -> list[tuple[int, int, int]]:
    return [PAL[n] for n in names]


@lru_cache(maxsize=4)
def ship_occupancy(size: int = 512) -> np.ndarray:
    """Fraction of ship plates carrying ink at each point, in ship-plate space.

    Measured from ``sprites/ship_class/*.png`` rather than assumed. Used as a
    placement probability field so damage lands on structure.

    NOTE: this makes the condition layer depend on the ship layer. If
    ``ship_class`` art changes, regenerate ``ship_condition`` too —
    ``tests/test_artgen_reproducible.py`` will flag the drift.
    """
    import cv2

    paths = sorted(SPRITES.glob("ship_class/*.png"))
    if not paths:
        raise FileNotFoundError(f"no ship_class plates under {SPRITES}")
    acc = np.zeros((size, size), dtype=np.float32)
    for path in paths:
        alpha = np.asarray(Image.open(path).convert("RGBA"))[:, :, 3]
        small = cv2.resize(alpha, (size, size), interpolation=cv2.INTER_AREA)
        acc += (small.astype(np.float32) / 255.0 > 0.15)
    return acc / len(paths)


@dataclass(frozen=True)
class ConditionSpec:
    key: str
    stops: list[tuple[int, int, int]]
    ink_color: str = "deep_navy"
    line_alpha: float = 0.70
    line_width: float = 5.0
    water_level: float | None = None
    """Waterline height in ship space; None means no engulfing water."""
    water_alpha: float = 0.72
    """Opacity of submerged water. Below 1 so the hull reads through it."""
    water_spread: float | None = 0.42
    """Half-width of the local swell; None makes the water a full-width plane."""
    tilt: float = 0.0
    """Waterline tilt in radians (listing)."""
    motif: Callable[["ConditionCtx"], None] | None = None
    notes: str = ""
    extras: dict = dc_field(default_factory=dict)


@dataclass
class ConditionCtx:
    spec: ConditionSpec
    size: int
    rng: np.random.Generator
    canvas: Canvas
    occ: np.ndarray
    """Occupancy field resampled to ``size``."""

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

    def sample_hull(self, n: int, *, y_range: tuple[float, float] | None = None,
                    min_occ: float = 0.30) -> list[tuple[float, float]]:
        """Draw ``n`` points weighted by how many ships have ink there.

        This is what keeps damage on the vessel: a point picked here is on ship
        structure for at least ``min_occ`` of the sixteen classes.
        """
        occ = self.occ.copy()
        lo, hi = y_range if y_range else HULL_BAND
        ys = np.linspace(0.0, 1.0, occ.shape[0], dtype=np.float32)[:, None]
        occ *= ((ys >= lo) & (ys <= hi)).astype(np.float32)
        occ[occ < min_occ] = 0.0
        total = occ.sum()
        if total <= 0:
            fx, fy = ship_to_canvas(0.5, (lo + hi) * 0.5)
            return [(self.size * fx, self.size * fy)] * n
        flat = (occ / total).ravel()
        idx = self.rng.choice(flat.size, size=n, p=flat)
        rows, cols = np.divmod(idx, occ.shape[1])
        h, w = occ.shape
        out: list[tuple[float, float]] = []
        for r, c in zip(rows, cols):
            u = (float(c) + float(self.rng.uniform(0, 1))) / w
            v = (float(r) + float(self.rng.uniform(0, 1))) / h
            cx, cy = ship_to_canvas(u, v)
            out.append((cx * self.size, cy * self.size))
        return out


# ------------------------------------------------------------------- water


def _surface_y(ctx: ConditionCtx, level: float) -> np.ndarray:
    """Per-column waterline y in canvas pixels.

    Unless the spec says otherwise the raised water is a *local swell* around
    the vessel that relaxes back to ``SEA_HORIZON`` at the frame edges. A
    full-width plane at a different height than the sea layer's own horizon
    puts two contradictory horizons in one picture; a swell reads as this ship
    settling into the water it is actually floating in.
    """
    s = ctx.size
    xs = np.linspace(0.0, 1.0, s, dtype=np.float32)
    if ctx.spec.water_spread is None:
        base = np.full_like(xs, level)
    else:
        # Centre the swell on the *vessel*, not the frame. ship_class is
        # anchored to one side, so a frame-centred bell raises water beside the
        # hull instead of around it.
        ship_cx = ship_to_canvas(0.5, 0.5)[0]
        bell = np.exp(-((xs - ship_cx) / ctx.spec.water_spread) ** 2)
        base = SEA_HORIZON + (level - SEA_HORIZON) * bell
    tilt = math.tan(ctx.spec.tilt) * (xs - 0.5)
    ripple = (np.sin(xs * 2 * math.pi * 3.1) * 0.004
              + np.sin(xs * 2 * math.pi * 7.7 + 1.3) * 0.0022)
    return (base + tilt + ripple).astype(np.float32) * s


def _submerged_mask(ctx: ConditionCtx, level: float) -> np.ndarray:
    """1 below the (possibly tilted) waterline, 0 above, softened at the edge."""
    s = ctx.size
    ys = np.arange(s, dtype=np.float32)[:, None]
    surface = _surface_y(ctx, level)[None, :]
    return smoothstep(surface - ctx.px(6.0), surface + ctx.px(14.0),
                      np.broadcast_to(ys, (s, s)))


def _draw_water(ctx: ConditionCtx, level: float) -> None:
    """Engulfing water: tint, surface rule, and wave ribbons riding the line."""
    s, rng = ctx.size, ctx.rng
    spec = ctx.spec
    sub = _submerged_mask(ctx, level)

    # tint deepens with depth below the surface, never a flat block
    ramp = ramp_image(spec.stops, s, s, min(level, SEA_HORIZON), 1.0)
    grain = value_noise(s, s, 8, rng)
    ctx.paint(sub * spec.water_alpha * (0.74 + 0.26 * grain), ramp)

    # the surface itself: a bright rule plus broken ribbons along it
    surface = _surface_y(ctx, level)
    m = ctx.ink_mask()
    pts = [(float(x), float(surface[int(x)]))
           for x in np.linspace(0, s - 1, 160)]
    ink.calligraphic_stroke(m, pts, ctx.px(5.0), ctx.px(2.0), taper=0.8)
    for _ in range(7):
        x0 = float(rng.uniform(-0.1, 0.7)) * s
        span = float(rng.uniform(0.25, 0.6)) * s
        amp = ctx.px(float(rng.uniform(8, 26)))
        seg = [(x, float(surface[int(np.clip(x, 0, s - 1))])
                + math.sin(x / (s * 0.14) * 2 * math.pi) * amp)
               for x in np.linspace(x0, x0 + span, 90)]
        ink.flow_bundle(m, seg, rng, count=3, spread=amp * 0.5,
                        width=ctx.px(3.6), pinch=0.6)
    for _ in range(5):
        x = float(rng.uniform(0.05, 0.95)) * s
        y = float(surface[int(np.clip(x, 0, s - 1))])
        ink.curl_flourish(m, x, y - ctx.px(26), ctx.px(float(rng.uniform(26, 62))),
                          rng, turns=float(rng.uniform(1.2, 2.0)),
                          width=ctx.px(3.4))
    ctx.paint(m, PAL[spec.ink_color], spec.line_alpha)
    ctx.paint(ctx.soft(m, 20.0) * 0.6, PAL["bone_white"], 0.30)


# ------------------------------------------------------------------ motifs


def motif_ripple(ctx: ConditionCtx) -> None:
    """Floating: the quiet common tier — a wake and a reflection, nothing more.

    Restraint is right for the common bucket, but the first pass was literally
    invisible over the sea plate. A wake spreading from the hull plus a
    shimmer band reads as "under way" without competing with the ship.
    """
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    cx, _ = ship_to_canvas(0.5, 0.6)
    cx *= s
    for i in range(7):
        y = s * (SEA_HORIZON + 0.014 * (i + 1))
        spread = 0.10 + 0.085 * i
        x0, x1 = cx - spread * s, cx + spread * s
        amp = ctx.px(9 + 7 * i)
        pts = [(x, y + math.sin(x / (s * 0.13) * 2 * math.pi) * amp)
               for x in np.linspace(x0, x1, 110)]
        ink.flow_bundle(m, pts, rng, count=3, spread=amp * 0.45,
                        width=ctx.px(5.0 - 0.35 * i), pinch=0.7)
    for _ in range(4):
        x = cx + float(rng.uniform(-0.34, 0.34)) * s
        y = s * (SEA_HORIZON + float(rng.uniform(0.02, 0.11)))
        ink.curl_flourish(m, x, y, ctx.px(float(rng.uniform(30, 70))), rng,
                          turns=float(rng.uniform(1.1, 1.8)), width=ctx.px(4.0))
    ctx.paint(m, PAL["bone_white"], 0.72)
    ctx.paint(ctx.soft(m, 9.0) * 0.8, PAL["sea_blue"], 0.42)
    # a shimmer of reflected hull just under the waterline
    y = np.linspace(0.0, 1.0, s, dtype=np.float32)[:, None]
    band = np.exp(-((y - (SEA_HORIZON + 0.03)) / 0.028) ** 2)
    ctx.paint(np.broadcast_to(band, (s, s)) * 0.30, PAL["bone_white"])


def motif_flood(ctx: ConditionCtx) -> None:
    """Water standing *inside* the vessel: pools on structure, spilling out."""
    rng = ctx.rng
    pools = ctx.ink_mask()
    lines = ctx.ink_mask()
    for cx, cy in ctx.sample_hull(7, y_range=(0.46, 0.72), min_occ=0.45):
        rx = ctx.px(float(rng.uniform(90, 230)))
        ry = rx * float(rng.uniform(0.16, 0.28))
        poly = [(cx + math.cos(a) * rx * float(rng.uniform(0.85, 1.15)),
                 cy + math.sin(a) * ry * float(rng.uniform(0.8, 1.2)))
                for a in np.linspace(0, 2 * math.pi, 22, endpoint=False)]
        ink.fill_poly(pools, poly, 1.0)
        ink.polyline(lines, poly, ctx.px(3.0), 1.0, closed=True)
        for _ in range(2):
            x = cx + float(rng.uniform(-rx, rx))
            ink.polyline(lines, [(x, cy), (x + ctx.px(float(rng.uniform(-30, 30))),
                                           cy + ctx.px(float(rng.uniform(80, 260))))],
                         ctx.px(2.6), 0.7)
    ctx.paint(pools * 0.55, PAL["sea_blue"], 0.62)
    ctx.paint(lines, PAL["deep_navy"], 0.70)


def motif_broken_mast(ctx: ConditionCtx) -> None:
    """A snapped spar: splintered stump, toppled mast, draped rigging, splash.

    A single tapered pole reads as a stick lying on the picture. What makes it
    read as *breakage* is the pairing — a stump that stayed up, a spar that
    came down, and rigging still connecting the two.
    """
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    ax, ay = ctx.sample_hull(1, y_range=(0.24, 0.46), min_occ=0.25)[0]

    # the stump that stayed standing, with a splintered crown
    stump_h = s * float(rng.uniform(0.06, 0.11))
    ink.calligraphic_stroke(m, [(ax, ay + stump_h), (ax, ay)],
                            ctx.px(26), ctx.px(17), taper=1.0)
    for _ in range(9):
        h = float(rng.uniform(0.25, 1.0)) * stump_h * 0.55
        lean = float(rng.uniform(-0.5, 0.5))
        ink.calligraphic_stroke(
            m, [(ax + float(rng.uniform(-9, 9)) * ctx.k, ay),
                (ax + lean * h, ay - h)], ctx.px(6.5), ctx.px(1.5), taper=1.4)

    # the fallen spar
    side = 1.0 if rng.random() < 0.5 else -1.0
    ang = side * float(rng.uniform(0.42, 0.80))
    length = s * float(rng.uniform(0.34, 0.46))
    tip = (ax + math.cos(ang) * length * side, ay + abs(math.sin(ang)) * length)
    ink.calligraphic_stroke(m, [(ax, ay - stump_h * 0.1), tip],
                            ctx.px(24), ctx.px(8), taper=1.0)
    # cross-spars so it reads as a mast, not a pole
    for t in (0.34, 0.62, 0.84):
        px_ = ax + (tip[0] - ax) * t
        py = ay + (tip[1] - ay) * t
        yard = length * (0.20 - 0.07 * t)
        perp = ang + math.pi / 2
        ink.calligraphic_stroke(
            m, [(px_ - math.cos(perp) * yard, py - math.sin(perp) * yard),
                (px_ + math.cos(perp) * yard, py + math.sin(perp) * yard)],
            ctx.px(9), ctx.px(4), taper=1.0)

    ctx.paint(m, PAL[ctx.spec.ink_color], ctx.spec.line_alpha)

    # rigging: bundles sagging from the fallen spar into the water
    rig = ctx.ink_mask()
    for _ in range(7):
        t = float(rng.uniform(0.2, 1.0))
        px_, py = ax + (tip[0] - ax) * t, ay + (tip[1] - ay) * t
        end = (px_ + float(rng.uniform(-0.16, 0.16)) * s, s * SEA_HORIZON)
        sag = ctx.px(float(rng.uniform(60, 190)))
        spine = ink.catmull_rom(
            [(px_, py), ((px_ + end[0]) / 2, (py + end[1]) / 2 + sag), end],
            samples_per_span=18)
        ink.flow_bundle(rig, spine, rng, count=2, spread=ctx.px(9),
                        width=ctx.px(3.4), pinch=0.8)
    ctx.paint(rig, PAL["slate_gray"], 0.72)

    sp = ctx.ink_mask()
    ink.sparks(sp, rng, 200,
               x_range=(max(0.0, tip[0] / s - 0.15), min(1.0, tip[0] / s + 0.15)),
               y_range=(SEA_HORIZON - 0.11, SEA_HORIZON + 0.02),
               size=(ctx.px(6), ctx.px(24)), rise=2.4)
    ctx.paint(sp, PAL["bone_white"], 0.85)
    ctx.paint(ctx.soft(sp, 18.0) * 0.7, PAL["pale_blue"], 0.48)


def motif_burning(ctx: ConditionCtx) -> None:
    """Flame tongues and a smoke column rising off ship structure."""
    s, rng = ctx.size, ctx.rng
    flame = ctx.ink_mask()
    for cx, cy in ctx.sample_hull(9, y_range=(0.38, 0.66), min_occ=0.40):
        ink.tendril(flame, cx, cy, s * float(rng.uniform(0.14, 0.30)),
                    -math.pi / 2 + float(rng.uniform(-0.55, 0.55)), rng,
                    width=ctx.px(float(rng.uniform(5, 9))),
                    curl_radius=float(rng.uniform(0.10, 0.22)), sway=0.5)
    ctx.paint(flame, PAL["ember_orange"], 0.80)
    ctx.paint(ctx.soft(flame, 26.0) * 0.9, PAL["crimson"], 0.45)

    embers = ctx.ink_mask()
    ink.sparks(embers, rng, 300, y_range=(0.12, 0.62),
               size=(ctx.px(4), ctx.px(16)), rise=2.6)
    ctx.paint(np.clip(embers + ctx.soft(embers, 10.0) * 0.6, 0, 1),
              PAL["pale_gold"], 0.85)

    smoke = ctx.ink_mask()
    for cx, cy in ctx.sample_hull(4, y_range=(0.34, 0.56), min_occ=0.40):
        ink.tendril(smoke, cx, cy, s * float(rng.uniform(0.28, 0.46)),
                    -math.pi / 2 + float(rng.uniform(-0.4, 0.4)), rng,
                    width=ctx.px(float(rng.uniform(6, 11))),
                    curl_radius=float(rng.uniform(0.12, 0.26)), sway=0.45)
    ctx.paint(smoke, PAL["slate_gray"], 0.42)
    ctx.paint(ctx.soft(smoke, 46.0) * 0.8, PAL["ash_gray"], 0.30)


def motif_salvage(ctx: ConditionCtx) -> None:
    """Crane jib, hook block, lifting slings and marker floats.

    The first pass was three hairlines from the top edge, which read as
    scratches on the scan. Weight is what sells salvage gear: a jib with real
    thickness entering the frame, cables that visibly carry load, and a hook
    block big enough to see.
    """
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()

    # jib swinging in from a corner
    from_left = rng.random() < 0.5
    root = (-s * 0.06 if from_left else s * 1.06, s * float(rng.uniform(0.02, 0.10)))
    elbow = (s * (0.30 if from_left else 0.70), s * 0.06)
    head = (s * float(rng.uniform(0.40, 0.60)), s * float(rng.uniform(0.10, 0.17)))
    ink.calligraphic_stroke(m, [root, elbow], ctx.px(30), ctx.px(20), taper=1.0)
    ink.calligraphic_stroke(m, [elbow, head], ctx.px(20), ctx.px(13), taper=1.0)
    for t in np.linspace(0.06, 0.94, 9):          # lattice bracing
        a = (root[0] + (elbow[0] - root[0]) * t, root[1] + (elbow[1] - root[1]) * t)
        b = (root[0] + (elbow[0] - root[0]) * min(1.0, t + 0.11),
             root[1] + (elbow[1] - root[1]) * min(1.0, t + 0.11) + ctx.px(34))
        ink.polyline(m, [a, b], ctx.px(5.0), 0.85)

    # cables down to a hook block sitting on the hull
    hooks = ctx.sample_hull(2, y_range=(0.28, 0.52), min_occ=0.35)
    for hx, hy in hooks:
        ink.calligraphic_stroke(m, [head, (hx, hy)], ctx.px(7.0), ctx.px(5.0), taper=1.0)
        bw, bh = ctx.px(46), ctx.px(64)
        ink.polyline(m, [(hx - bw, hy), (hx + bw, hy),
                         (hx + bw * 0.7, hy + bh), (hx - bw * 0.7, hy + bh)],
                     ctx.px(6.0), 1.0, closed=True)
        r = ctx.px(40)
        ink.calligraphic_stroke(
            m, ink.spiral(hx, hy + bh + r, r, r * 0.9, 0.72, phase=-1.3, samples=70),
            ctx.px(8.0), ctx.px(5.0), taper=0.9)

    # slings passing under the hull
    for _ in range(2):
        y = s * float(rng.uniform(0.70, 0.80))
        x0 = float(rng.uniform(0.20, 0.36)) * s
        x1 = x0 + float(rng.uniform(0.28, 0.42)) * s
        ink.calligraphic_stroke(
            m, ink.catmull_rom([(x0, y - s * 0.18), ((x0 + x1) / 2, y),
                                (x1, y - s * 0.18)], samples_per_span=16),
            ctx.px(9.0), ctx.px(6.0), taper=0.9)
    ctx.paint(m, PAL["bronze"], ctx.spec.line_alpha)

    floats = ctx.ink_mask()
    for _ in range(6):
        x = float(rng.uniform(0.06, 0.94)) * s
        y = s * (SEA_HORIZON - 0.004)
        r = ctx.px(float(rng.uniform(20, 34)))
        ink.polyline(floats, [(x + math.cos(a) * r, y + math.sin(a) * r * 0.75)
                              for a in np.linspace(0, 2 * math.pi, 26)],
                     ctx.px(5.0), 1.0, closed=True)
        ink.polyline(floats, [(x - r, y), (x + r, y)], ctx.px(4.0), 0.9)
    ctx.paint(floats, PAL["ember_orange"], 0.88)


def motif_split(ctx: ConditionCtx) -> None:
    """A hull torn in two: zig-zag tear, dark void, bright torn edge, spill.

    A smooth-sided gap reads as a smear. Metal fails in jagged steps, and the
    torn edge catching light is what makes the void read as depth rather than
    a stain.
    """
    s, rng = ctx.size, ctx.rng
    gap = ctx.ink_mask()
    edges = ctx.ink_mask()
    lip = ctx.ink_mask()

    cx, cy = ctx.sample_hull(1, y_range=(0.46, 0.64), min_occ=0.50)[0]
    lean = float(rng.uniform(-0.30, 0.30))
    top, bot = cy - s * 0.19, cy + s * 0.24
    half = ctx.px(float(rng.uniform(24, 44)))

    left, right = [], []
    steps = 19
    for i in range(steps):
        t = i / (steps - 1)
        y = top + (bot - top) * t
        axis = cx + lean * (y - cy)
        w = half * (0.30 + 1.5 * math.sin(math.pi * t) ** 0.7)
        # alternate the jag so the edges interlock like torn plate
        jag = ctx.px(42) * (1 if i % 2 else -1) * float(rng.uniform(0.6, 1.6))
        left.append((axis - w + jag, y))
        right.append((axis + w + jag * 0.6, y))

    ink.fill_poly(gap, left + right[::-1], 1.0)
    for side in (left, right):
        ink.calligraphic_stroke(edges, side, ctx.px(11.0), ctx.px(3.5), taper=1.0)
        # torn lip catching the light, offset outward — this is what makes the
        # void read as depth rather than a stain
        off = ctx.px(16) * (-1 if side is left else 1)
        ink.calligraphic_stroke(lip, [(x + off, y) for x, y in side],
                                ctx.px(9.0), ctx.px(3.0), taper=1.0)

    # the void is darkest at mid-height and opens out at both ends, so the
    # hull's own linework still reads through the shallow parts of the tear
    ys = np.linspace(0.0, 1.0, s, dtype=np.float32)[:, None]
    depth = np.exp(-(((ys * s - (top + bot) / 2) / ((bot - top) * 0.42)) ** 2))
    ctx.paint(gap * depth * 0.80, PAL["ink_black"], 0.88)
    ctx.paint(edges, PAL["deep_ink"], 0.92)
    ctx.paint(ctx.soft(lip, 5.0), PAL["bone_white"], 0.80)

    # plating peeled back around the tear
    deb = ctx.ink_mask()
    for _ in range(20):
        t = float(rng.uniform(0.05, 0.95))
        y = top + (bot - top) * t
        axis = cx + lean * (y - cy)
        side = 1 if rng.random() < 0.5 else -1
        w = half * (0.30 + 1.5 * math.sin(math.pi * t) ** 0.7)
        base = (axis + side * w, y)
        out = (base[0] + side * ctx.px(float(rng.uniform(20, 90))),
               y + ctx.px(float(rng.uniform(-50, 50))))
        ink.calligraphic_stroke(deb, [base, out], ctx.px(6.0), ctx.px(1.6), taper=1.3)
    ctx.paint(deb, PAL["deep_ink"], 0.75)

    # water pouring through the breach
    spill = ctx.ink_mask()
    for _ in range(9):
        x = cx + float(rng.uniform(-0.06, 0.06)) * s
        y0 = cy + float(rng.uniform(-0.02, 0.10)) * s
        pts = [(x + math.sin(k * 0.6) * ctx.px(22), y0 + k * ctx.px(46))
               for k in range(9)]
        ink.flow_bundle(spill, ink.catmull_rom(pts, samples_per_span=8), rng,
                        count=3, spread=ctx.px(16), width=ctx.px(4.4), pinch=0.7)
    ctx.paint(spill, PAL["sea_blue"], 0.70)


def motif_ghost(ctx: ConditionCtx) -> None:
    """Spectral echo: the occupancy silhouette offset and blurred.

    Deriving the echo from the measured field is what lets one sprite trace
    sixteen different hulls — it is approximately the shape underneath it.
    """
    s, rng = ctx.size, ctx.rng
    import cv2

    occ = cv2.resize(ctx.occ, (s, s), interpolation=cv2.INTER_CUBIC)
    silhouette = np.clip((occ - 0.18) / 0.5, 0.0, 1.0).astype(np.float32)
    for i, (dx, dy, sigma, alpha) in enumerate((
            (0.035, -0.018, 26.0, 0.34), (-0.028, 0.014, 44.0, 0.24))):
        shifted = np.roll(silhouette, (int(dy * s), int(dx * s)), axis=(0, 1))
        col = PAL["pale_green"] if i == 0 else PAL["lavender"]
        ctx.paint(ctx.soft(shifted, sigma), col, alpha)
    # dissolve: the hull fades out toward its base
    y = np.linspace(0.0, 1.0, s, dtype=np.float32)[:, None]
    fade = smoothstep(0.86, 0.55, y) * silhouette
    ctx.paint(ctx.soft(fade, 14.0), PAL["bone_white"], 0.30)
    # wisps peeling off
    m = ctx.ink_mask()
    for cx, cy in ctx.sample_hull(7, y_range=(0.34, 0.72), min_occ=0.30):
        ink.tendril(m, cx, cy, s * float(rng.uniform(0.12, 0.26)),
                    float(rng.uniform(-math.pi, math.pi)), rng,
                    width=ctx.px(float(rng.uniform(3, 6))),
                    curl_radius=float(rng.uniform(0.12, 0.28)), sway=0.5,
                    bundle=3)
    ctx.paint(ctx.soft(m, 6.0), PAL["pale_green"], 0.42)


def motif_rebuilt(ctx: ConditionCtx) -> None:
    """Scaffolding, riveted patch plates and welding light — the payoff.

    Drawn as a perfect axis-aligned grid it reads as a wireframe box floating
    over the picture. Real staging is irregular: posts of unequal height,
    planks that overhang, diagonal braces, and the arc-light that says work is
    happening *now*.
    """
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()

    x0, x1 = s * 0.17, s * 0.83
    y_top, y_bot = s * 0.33, s * 0.79
    posts = 7
    post_x = []
    for i in range(posts):
        x = x0 + (x1 - x0) * i / (posts - 1) + float(rng.uniform(-0.018, 0.018)) * s
        top = y_top + float(rng.uniform(-0.05, 0.05)) * s
        bot = y_bot + float(rng.uniform(-0.03, 0.05)) * s
        ink.calligraphic_stroke(m, [(x, top), (x, bot)], ctx.px(8.0), ctx.px(6.0),
                                taper=1.0)
        post_x.append((x, top, bot))
    # planks: run between neighbouring posts, overhanging a little
    for j in range(4):
        y = y_top + (y_bot - y_top) * (j / 3) + float(rng.uniform(-0.012, 0.012)) * s
        for i in range(posts - 1):
            xa = post_x[i][0] - ctx.px(float(rng.uniform(0, 34)))
            xb = post_x[i + 1][0] + ctx.px(float(rng.uniform(0, 34)))
            if rng.random() < 0.82:
                ink.calligraphic_stroke(m, [(xa, y), (xb, y + ctx.px(
                    float(rng.uniform(-10, 10))))], ctx.px(7.0), ctx.px(5.0), taper=1.0)
    for i in range(posts - 1):
        if rng.random() < 0.7:
            ink.polyline(m, [(post_x[i][0], post_x[i][2]),
                             (post_x[i + 1][0], post_x[i + 1][1])], ctx.px(3.4), 0.7)
    ctx.paint(m, PAL["bronze"], 0.76)

    patches = ctx.ink_mask()
    rivets = ctx.ink_mask()
    for cx, cy in ctx.sample_hull(5, y_range=(0.46, 0.74), min_occ=0.45):
        w = ctx.px(float(rng.uniform(90, 210)))
        h = w * float(rng.uniform(0.40, 0.70))
        poly = [(cx - w, cy - h), (cx + w, cy - h * 0.78),
                (cx + w * 0.9, cy + h), (cx - w * 1.05, cy + h * 0.86)]
        ink.fill_poly(patches, poly, 1.0)
        ink.polyline(rivets, poly, ctx.px(5.0), 1.0, closed=True)
        for t in np.linspace(0.08, 0.92, 8):
            for side in (-1, 1):
                rx = cx - w + 2 * w * t
                ry = cy + side * h * 0.84
                ink.polyline(rivets, [(rx, ry), (rx + 0.5, ry)], ctx.px(9.0), 1.0)
    ctx.paint(patches * 0.45, PAL["ash_gray"], 0.60)
    ctx.paint(rivets, PAL["slate_gray"], 0.85)

    sparks = ctx.ink_mask()
    glow = ctx.ink_mask()
    for cx, cy in ctx.sample_hull(3, y_range=(0.44, 0.72), min_occ=0.45):
        for _ in range(90):
            a = float(rng.uniform(0, 2 * math.pi))
            r = ctx.px(float(rng.uniform(8, 165)))
            ink.polyline(sparks, [(cx, cy), (cx + math.cos(a) * r,
                                             cy + math.sin(a) * r)],
                         ctx.px(2.2), float(rng.uniform(0.25, 1.0)))
        rr = ctx.px(26)
        ink.fill_poly(glow, [(cx + math.cos(a) * rr, cy + math.sin(a) * rr)
                             for a in np.linspace(0, 2 * math.pi, 20)], 1.0)
    ctx.paint(np.clip(sparks + ctx.soft(sparks, 14.0) * 0.8, 0, 1),
              PAL["pale_gold"], 0.92)
    ctx.paint(ctx.soft(glow, 40.0) * 1.4, PAL["sand"], 0.55)
    ctx.paint(glow, PAL["bone_white"], 0.9)


def motif_underwater(ctx: ConditionCtx) -> None:
    """Fully submerged: bubble columns and light shafts over the engulfed hull."""
    s, rng = ctx.size, ctx.rng
    bub = ctx.ink_mask()
    for cx, _ in ctx.sample_hull(6, y_range=(0.40, 0.78), min_occ=0.35):
        x = cx
        y = s * float(rng.uniform(0.55, 0.75))
        while y > -s * 0.05:
            r = ctx.px(float(rng.uniform(5, 22)))
            ink.polyline(bub, [(x + math.cos(a) * r, y + math.sin(a) * r)
                               for a in np.linspace(0, 2 * math.pi, 18)],
                         ctx.px(2.6), 1.0, closed=True)
            y -= float(rng.uniform(ctx.px(50), ctx.px(150)))
            x += float(rng.uniform(-ctx.px(30), ctx.px(30)))
    ctx.paint(bub, PAL["bone_white"], 0.62)

    shafts = ctx.ink_mask()
    for _ in range(9):
        x = float(rng.uniform(0.0, 1.0)) * s
        w = ctx.px(float(rng.uniform(30, 90)))
        lean = float(rng.uniform(-0.12, 0.12)) * s
        ink.fill_poly(shafts, [(x - w, 0), (x + w, 0),
                               (x + w * 0.3 + lean, s), (x - w * 0.3 + lean, s)], 1.0)
    ctx.paint(ctx.soft(shafts, 44.0) * 0.55, PAL["pale_blue"], 0.28)


# -------------------------------------------------------------------- specs

CONDITION_SPECS: dict[str, ConditionSpec] = {
    "floating": ConditionSpec(
        "floating", _c("pale_blue", "steel_blue"), ink_color="sea_blue",
        line_alpha=0.44, motif=motif_ripple,
        notes="common — deliberately the quietest overlay in the set"),
    "listing": ConditionSpec(
        "listing", _c("steel_blue", "sea_blue", "navy"), ink_color="deep_navy",
        water_level=SEA_HORIZON + 0.025, water_alpha=0.58, water_spread=0.46,
        tilt=math.radians(9.0),
        notes="a tilted waterline reads as a tilted ship — an overlay cannot "
              "rotate the hull beneath it, but it can rotate the sea"),
    "half_sunk": ConditionSpec(
        "half_sunk", _c("sea_blue", "navy", "deep_navy"), ink_color="deep_navy",
        water_level=0.470, water_alpha=0.72, water_spread=0.38),
    "flooded": ConditionSpec(
        "flooded", _c("sea_blue", "navy"), ink_color="deep_navy",
        line_alpha=0.70, motif=motif_flood),
    "broken_mast": ConditionSpec(
        "broken_mast", _c("slate_gray", "deep_ink"), ink_color="deep_ink",
        line_alpha=0.82, motif=motif_broken_mast),
    "burning": ConditionSpec(
        "burning", _c("ember_orange", "crimson"), ink_color="maroon",
        line_alpha=0.80, motif=motif_burning),
    "being_salvaged": ConditionSpec(
        "being_salvaged", _c("bronze", "amber"), ink_color="bronze",
        line_alpha=0.78, motif=motif_salvage),
    "split_hull": ConditionSpec(
        "split_hull", _c("deep_ink", "ink_black"), ink_color="ink_black",
        line_alpha=0.85, motif=motif_split),
    "fully_underwater": ConditionSpec(
        "fully_underwater", _c("navy", "deep_navy", "abyss_navy"),
        ink_color="abyss_navy", water_level=0.055, water_alpha=0.62,
        water_spread=None,
        motif=motif_underwater),
    "ghost": ConditionSpec(
        "ghost", _c("pale_green", "teal_green"), ink_color="teal_green",
        line_alpha=0.40, motif=motif_ghost),
    "rebuilt": ConditionSpec(
        "rebuilt", _c("bronze", "amber", "gold"), ink_color="bronze",
        line_alpha=0.78, motif=motif_rebuilt,
        notes="legendary — scaffolding, patches, welding light"),
}


# ------------------------------------------------------------------ render


def render(trait_key: str, size: int = 2048) -> Canvas:
    """Render one condition overlay. Deterministic in ``trait_key``."""
    import cv2

    spec = CONDITION_SPECS[trait_key]
    rng = rng_for(f"ship_condition/{trait_key}/v1")
    canvas = Canvas(size)
    occ = cv2.resize(ship_occupancy(), (min(size, 512),) * 2,
                     interpolation=cv2.INTER_AREA)
    ctx = ConditionCtx(spec=spec, size=size, rng=rng, canvas=canvas, occ=occ)

    if spec.water_level is not None:
        _draw_water(ctx, spec.water_level)
    if spec.motif is not None:
        spec.motif(ctx)

    canvas.multiply_alpha(MAX_ALPHA)
    return canvas


def all_keys() -> list[str]:
    return list(CONDITION_SPECS)
