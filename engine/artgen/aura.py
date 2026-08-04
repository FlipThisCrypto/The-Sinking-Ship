# SPDX-License-Identifier: MIT
"""Aura / effect layer (z-order 11 — the topmost plate).

Two constraints shape every plate here, and they pull against each other.

**It must be spectacular.** Only ~8% of the supply carries an aura and every
trait sits in the epic/legendary/mythic buckets, so a buyer who rolls one
should see it immediately at thumbnail size.

**It must not bury the face.** This is the last layer composited — it draws
over eyes, mouth and hat. So the light is built to *wrap* the figure: emission
concentrates in a ring around the head and shoulders and falls away toward the
centre, and ``FACE_GUARD`` explicitly attenuates whatever survives inside the
head ellipse. Aura is rim light, not a filter over the portrait.

Geometry is measured, not guessed. Compositing the body plate at scale 0.84
anchored to the bottom puts the figure at canvas y 0.16..1.0 with its
horizontal centre of mass at x 0.519 and the head mass peaking around
y 0.33 — hence ``FOCUS``.
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

FOCUS = (0.52, 0.33)
"""Head centre in canvas coordinates — where emission originates."""

TORSO = (0.52, 0.58)
"""Centre of the figure's mass; the broader glows key off this."""

FACE_GUARD = (0.115, 0.145)
"""Radii (x, y) of the ellipse around FOCUS whose alpha is pulled down."""

FACE_GUARD_KEEP = 0.34
"""Fraction of alpha retained at the centre of the guard."""

MAX_ALPHA = 0.90


def _c(*names: str) -> list[tuple[int, int, int]]:
    return [PAL[n] for n in names]


@dataclass(frozen=True)
class AuraSpec:
    key: str
    colors: list[tuple[int, int, int]]
    """Emission colours, brightest first."""
    bloom: float = 0.45
    """Strength of the broad radial wash around the figure."""
    bloom_radius: float = 0.46
    ink_color: str = "bone_white"
    line_alpha: float = 0.75
    guard: float = FACE_GUARD_KEEP
    """Per-trait override of how much aura survives over the face."""
    motif: Callable[["AuraCtx"], None] | None = None
    notes: str = ""
    extras: dict = dc_field(default_factory=dict)


@dataclass
class AuraCtx:
    spec: AuraSpec
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

    def at(self, point: tuple[float, float]) -> tuple[float, float]:
        return point[0] * self.size, point[1] * self.size

    def radial(self, centre: tuple[float, float], radius: float,
               falloff: float = 2.0) -> np.ndarray:
        """Normalised radial falloff, 1 at the centre and 0 at ``radius``."""
        s = self.size
        cx, cy = self.at(centre)
        ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
        d = np.hypot(xs - cx, ys - cy) / max(1.0, radius * s)
        return np.clip(1.0 - d, 0.0, 1.0) ** falloff

    def ring(self, centre: tuple[float, float], radius: float,
             width: float) -> np.ndarray:
        """A soft annulus — the shape that lights a subject without covering it."""
        s = self.size
        cx, cy = self.at(centre)
        ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
        d = np.hypot(xs - cx, ys - cy) / max(1.0, s)
        return np.exp(-(((d - radius) / max(1e-4, width)) ** 2)).astype(np.float32)

    def rays(self, mask: np.ndarray, centre: tuple[float, float], count: int,
             *, r0: float, r1: float, width: float, jitter: float = 1.0,
             lobes: int = 0) -> np.ndarray:
        """Radiating spokes with uneven lengths — regular spokes read as a wheel."""
        s, rng = self.size, self.rng
        cx, cy = self.at(centre)
        phase = float(rng.uniform(0, 2 * math.pi))
        for i in range(count):
            a = i / count * 2 * math.pi + float(rng.uniform(-0.01, 0.01)) * jitter
            lobe = 1.0
            if lobes:
                lobe = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(a * lobes + phase))
            ln = s * (r0 + (r1 - r0) * lobe * float(rng.uniform(0.35, 1.0)))
            ink.calligraphic_stroke(
                mask,
                [(cx + math.cos(a) * s * r0 * 0.9, cy + math.sin(a) * s * r0 * 0.9),
                 (cx + math.cos(a) * ln, cy + math.sin(a) * ln)],
                self.px(width), self.px(width * 0.18), taper=1.6,
                intensity=float(rng.uniform(0.4, 1.0)))
        return mask


# ------------------------------------------------------------------ motifs


def _wisps(ctx: AuraCtx, count: int, color, *, alpha: float = 0.6,
           inner: float = 0.16, outer: float = 0.34) -> None:
    """Curling tendrils orbiting the figure — the Amano flourish."""
    s, rng = ctx.size, ctx.rng
    m = ctx.ink_mask()
    cx, cy = ctx.at(TORSO)
    for _ in range(count):
        a = float(rng.uniform(0, 2 * math.pi))
        r = s * float(rng.uniform(inner, outer))
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.85
        ink.tendril(m, x, y, s * float(rng.uniform(0.10, 0.22)),
                    a + float(rng.uniform(-0.9, 0.9)), rng,
                    width=ctx.px(float(rng.uniform(3.5, 7.0))),
                    curl_radius=float(rng.uniform(0.12, 0.28)), sway=0.5,
                    bundle=3)
    ctx.paint(m, color, alpha)
    ctx.paint(ctx.soft(m, 26.0) * 0.8, color, alpha * 0.45)


def motif_magic_glow(ctx: AuraCtx) -> None:
    """Rising motes, orbiting wisps and a rune arc — the two magic glows."""
    s, rng = ctx.size, ctx.rng
    warm, cool = ctx.spec.colors[0], ctx.spec.colors[-1]
    _wisps(ctx, 9, warm, alpha=0.62)

    motes = ctx.ink_mask()
    ink.star_field(motes, rng, 220, y_range=(0.12, 0.92),
                   size_range=(ctx.px(3.0), ctx.px(11.0)), sparkle_frac=0.22)
    ctx.paint(np.clip(motes + ctx.soft(motes, 12.0) * 0.8, 0, 1), PAL["bone_white"], 0.72)
    ctx.paint(ctx.soft(motes, 44.0) * 1.2, warm, 0.42)

    # a broken arc of sigils behind the head
    arc = ctx.ink_mask()
    cx, cy = ctx.at(FOCUS)
    for i in range(15):
        a = -math.pi * 0.92 + i * (math.pi * 0.84) / 14
        r = s * 0.245
        gx, gy = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.92
        n = int(rng.integers(3, 6))
        poly = [(gx + math.cos(t) * ctx.px(28), gy + math.sin(t) * ctx.px(28))
                for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]
        ink.polyline(arc, poly, ctx.px(3.4), float(rng.uniform(0.5, 1.0)), closed=True)
    ctx.paint(arc, cool, 0.66)
    ctx.paint(ctx.soft(arc, 20.0), cool, 0.32)


def motif_crystal(ctx: AuraCtx) -> None:
    """Faceted shards orbiting the figure, with prismatic glints."""
    s, rng = ctx.size, ctx.rng
    body = ctx.ink_mask()
    facets = ctx.ink_mask()
    cx, cy = ctx.at(TORSO)
    for _ in range(17):
        a = float(rng.uniform(0, 2 * math.pi))
        r = s * float(rng.uniform(0.18, 0.42))
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.85
        h = ctx.px(float(rng.uniform(70, 210)))
        w = h * float(rng.uniform(0.24, 0.42))
        tilt = float(rng.uniform(-0.5, 0.5))
        pts = [(0, -h), (w, -h * 0.34), (w * 0.72, h * 0.62), (-w * 0.72, h * 0.62),
               (-w, -h * 0.34)]
        rot = [(x + px_ * math.cos(tilt) - py * math.sin(tilt),
                y + px_ * math.sin(tilt) + py * math.cos(tilt)) for px_, py in pts]
        ink.fill_poly(body, rot, 1.0)
        ink.polyline(facets, rot, ctx.px(4.0), 1.0, closed=True)
        for j in (0, 1, 4):
            ink.polyline(facets, [rot[j], rot[2]], ctx.px(2.6), 0.75)
    ctx.paint(body * 0.42, ctx.spec.colors[0], 0.74)
    ctx.paint(facets, PAL["bone_white"], 0.95)
    ctx.paint(ctx.soft(facets, 30.0) * 1.1, ctx.spec.colors[-1], 0.40)

    glints = ctx.ink_mask()
    ink.star_field(glints, rng, 90, y_range=(0.12, 0.9),
                   size_range=(ctx.px(2.0), ctx.px(7.0)), sparkle_frac=0.85)
    ctx.paint(np.clip(glints + ctx.soft(glints, 10.0), 0, 1), PAL["bone_white"], 0.8)


def motif_halo(ctx: AuraCtx) -> None:
    """A luminous ring tilted above the head, with light falling from it."""
    s, rng = ctx.size, ctx.rng
    cx, cy = ctx.at(FOCUS)
    cy -= s * 0.185
    m = ctx.ink_mask()
    rx, ry = s * 0.150, s * 0.044
    for k, scale in enumerate((1.0, 0.90, 0.80)):
        pts = [(cx + math.cos(a) * rx * scale, cy + math.sin(a) * ry * scale)
               for a in np.linspace(0, 2 * math.pi, 160)]
        ink.calligraphic_stroke(m, pts + [pts[0]], ctx.px(11 - 3 * k),
                                ctx.px(5 - 1.5 * k), taper=0.6)
    ctx.paint(np.clip(m + ctx.soft(m, 14.0), 0, 1), PAL["bone_white"], 0.92)
    ctx.paint(ctx.soft(m, 60.0) * 1.3, PAL["pale_gold"], 0.50)

    beams = ctx.ink_mask()
    for _ in range(22):
        a = float(rng.uniform(0, 2 * math.pi))
        x = cx + math.cos(a) * rx * 0.95
        length = s * float(rng.uniform(0.10, 0.30))
        ink.calligraphic_stroke(beams, [(x, cy + math.sin(a) * ry),
                                        (x + float(rng.uniform(-0.03, 0.03)) * s,
                                         cy + length)],
                                ctx.px(6.0), ctx.px(1.2), taper=1.8,
                                intensity=float(rng.uniform(0.3, 0.9)))
    ctx.paint(ctx.soft(beams, 10.0), PAL["sand"], 0.55)


def motif_laser(ctx: AuraCtx) -> None:
    """Beam flare across the eye line, with a hot core and streak artefacts."""
    s, rng = ctx.size, ctx.rng
    cx, cy = ctx.at(FOCUS)
    core = ctx.ink_mask()
    ink.calligraphic_stroke(core, [(-s * 0.1, cy - s * 0.012),
                                   (s * 1.1, cy + s * 0.012)],
                            ctx.px(16), ctx.px(16), taper=1.0)
    ctx.paint(np.clip(core + ctx.soft(core, 16.0), 0, 1), PAL["bone_white"], 0.95)
    ctx.paint(ctx.soft(core, 70.0) * 1.4, PAL["crimson"], 0.55)

    flare = ctx.ink_mask()
    ctx.rays(flare, (cx / s, cy / s), 46, r0=0.02, r1=0.30, width=6.0, lobes=2)
    ctx.paint(ctx.soft(flare, 8.0), PAL["coral"], 0.70)

    ghosts = ctx.ink_mask()
    for t in (-0.30, -0.16, 0.18, 0.34):
        gx = cx + t * s
        r = ctx.px(float(rng.uniform(30, 80)))
        ink.polyline(ghosts, [(gx + math.cos(a) * r, cy + math.sin(a) * r)
                              for a in np.linspace(0, 2 * math.pi, 40)],
                     ctx.px(4.0), 0.8, closed=True)
    ctx.paint(ghosts, PAL["rose_ash"], 0.55)


def motif_ghost_fade(ctx: AuraCtx) -> None:
    """Cold dissolve — the figure coming apart into drifting light."""
    s, rng = ctx.size, ctx.rng
    _wisps(ctx, 15, PAL["pale_blue"], alpha=0.68, inner=0.10, outer=0.40)

    flecks = ctx.ink_mask()
    for _ in range(650):
        x = float(rng.normal(TORSO[0], 0.17)) * s
        y = float(rng.normal(TORSO[1], 0.22)) * s
        w = ctx.px(float(rng.uniform(6, 34)))
        h = ctx.px(float(rng.uniform(2, 7)))
        ink.polyline(flecks, [(x - w, y), (x + w, y)], h,
                     float(rng.uniform(0.2, 0.8)))
    # sparser toward the top: the dissolve drifts upward and thins out
    ys = np.linspace(0.0, 1.0, s, dtype=np.float32)[:, None]
    ctx.paint(flecks * smoothstep(0.05, 0.55, ys), PAL["bone_white"], 0.92)
    ctx.paint(ctx.soft(flecks, 18.0) * 1.2, PAL["pale_blue"], 0.55)
    ctx.paint(ctx.soft(flecks, 46.0) * 1.2, PAL["lavender"], 0.42)


def motif_radiance(ctx: AuraCtx) -> None:
    """Full sunburst — the legendary; the loudest plate in the set."""
    rng = ctx.rng
    m = ctx.ink_mask()
    ctx.rays(m, FOCUS, 130, r0=0.10, r1=0.62, width=9.0, lobes=3)
    ctx.paint(np.clip(m + ctx.soft(m, 18.0) * 0.9, 0, 1), PAL["pale_gold"], 0.82)
    ctx.paint(ctx.soft(m, 80.0) * 1.3, PAL["gold"], 0.45)

    motes = ctx.ink_mask()
    ink.star_field(motes, rng, 260, y_range=(0.08, 0.95),
                   size_range=(ctx.px(3.0), ctx.px(12.0)), sparkle_frac=0.35)
    ctx.paint(np.clip(motes + ctx.soft(motes, 12.0), 0, 1), PAL["bone_white"], 0.85)
    ctx.paint(ctx.soft(motes, 46.0) * 1.2, PAL["amber"], 0.40)


def motif_chia_bloom(ctx: AuraCtx) -> None:
    """Mythic: a green bloom of sprouting filigree with gold ornament."""
    s, rng = ctx.size, ctx.rng
    _wisps(ctx, 11, PAL["bright_green"], alpha=0.66, inner=0.13, outer=0.36)

    leaves = ctx.ink_mask()
    veins = ctx.ink_mask()
    cx, cy = ctx.at(TORSO)
    for _ in range(22):
        a = float(rng.uniform(0, 2 * math.pi))
        r = s * float(rng.uniform(0.16, 0.40))
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.85
        ln = ctx.px(float(rng.uniform(95, 220)))
        ang = a + float(rng.uniform(-0.6, 0.6))
        tip = (x + math.cos(ang) * ln, y + math.sin(ang) * ln)
        perp = ang + math.pi / 2
        bulge = ln * 0.34
        left = (x + math.cos(ang) * ln * 0.5 + math.cos(perp) * bulge,
                y + math.sin(ang) * ln * 0.5 + math.sin(perp) * bulge)
        right = (x + math.cos(ang) * ln * 0.5 - math.cos(perp) * bulge,
                 y + math.sin(ang) * ln * 0.5 - math.sin(perp) * bulge)
        ink.calligraphic_stroke(leaves, ink.catmull_rom([(x, y), left, tip]),
                                ctx.px(6.0), ctx.px(1.6), taper=1.3)
        ink.calligraphic_stroke(leaves, ink.catmull_rom([(x, y), right, tip]),
                                ctx.px(6.0), ctx.px(1.6), taper=1.3)
        ink.polyline(veins, [(x, y), tip], ctx.px(2.2), 0.7)
    ctx.paint(leaves, PAL["chia_green"], 0.92)
    ctx.paint(veins, PAL["gold"], 0.80)
    ctx.paint(ctx.soft(leaves, 40.0) * 1.2, PAL["bright_green"], 0.38)

    motes = ctx.ink_mask()
    ink.star_field(motes, rng, 150, y_range=(0.12, 0.92),
                   size_range=(ctx.px(3.0), ctx.px(9.0)), sparkle_frac=0.4)
    ctx.paint(np.clip(motes + ctx.soft(motes, 10.0), 0, 1), PAL["pale_gold"], 0.80)


def motif_corruption(ctx: AuraCtx) -> None:
    """Mythic: the signal breaking up — torn bands, shards and static.

    Rendered as ink displacement rather than digital RGB-split, so the glitch
    stays inside the illustration's medium instead of reading as a screenshot.
    """
    s, rng = ctx.size, ctx.rng
    bands = ctx.ink_mask()
    for _ in range(16):
        y = float(rng.uniform(0.14, 0.94)) * s
        h = ctx.px(float(rng.uniform(6, 44)))
        x0 = float(rng.uniform(0.02, 0.55)) * s
        w = float(rng.uniform(0.16, 0.52)) * s
        ink.fill_poly(bands, [(x0, y), (x0 + w, y - h * 0.3),
                              (x0 + w, y + h), (x0, y + h * 0.7)], 1.0)
    ctx.paint(bands * 0.55, PAL["deep_violet"], 0.70)
    ctx.paint(ctx.soft(bands, 18.0) * 0.9, PAL["amethyst"], 0.40)

    shards = ctx.ink_mask()
    cx, cy = ctx.at(TORSO)
    for _ in range(30):
        a = float(rng.uniform(0, 2 * math.pi))
        r = s * float(rng.uniform(0.10, 0.42))
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.9
        n = int(rng.integers(3, 5))
        rr = ctx.px(float(rng.uniform(18, 72)))
        poly = [(x + math.cos(t) * rr * float(rng.uniform(0.4, 1.3)),
                 y + math.sin(t) * rr * float(rng.uniform(0.4, 1.3)))
                for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]
        ink.polyline(shards, poly, ctx.px(3.6), 1.0, closed=True)
    ctx.paint(shards, PAL["ink_black"], 0.80)

    static = value_noise(s, s, 260, rng)
    speckle = (static > 0.86).astype(np.float32)
    band_env = np.zeros((s, 1), dtype=np.float32)
    for _ in range(9):
        y0 = float(rng.uniform(0.1, 0.95))
        h = float(rng.uniform(0.01, 0.05))
        ys = np.linspace(0.0, 1.0, s, dtype=np.float32)[:, None]
        band_env = np.maximum(band_env, np.exp(-(((ys - y0) / h) ** 2)))
    ctx.paint(speckle * band_env, PAL["amethyst"], 0.72)


# -------------------------------------------------------------------- specs

AURA_SPECS: dict[str, AuraSpec] = {
    "green_magic_glow": AuraSpec(
        "green_magic_glow", _c("bright_green", "chia_green", "teal_green"),
        bloom=0.42, motif=motif_magic_glow),
    "purple_magic_glow": AuraSpec(
        "purple_magic_glow", _c("amethyst", "violet", "deep_violet"),
        bloom=0.42, motif=motif_magic_glow),
    "crystal_shimmer": AuraSpec(
        "crystal_shimmer", _c("pale_blue", "steel_blue", "lavender"),
        bloom=0.34, motif=motif_crystal),
    "halo_light": AuraSpec(
        "halo_light", _c("pale_gold", "sand", "bone_white"),
        bloom=0.38, bloom_radius=0.38, guard=0.55, motif=motif_halo,
        notes="the ring sits above the head, so the face needs less guarding"),
    "laser_bloom": AuraSpec(
        "laser_bloom", _c("crimson", "coral", "rose_ash"),
        bloom=0.30, guard=0.62, motif=motif_laser,
        notes="the beam is *meant* to cross the eye line"),
    "ghost_fade": AuraSpec(
        "ghost_fade", _c("pale_blue", "lavender", "ash_gray"),
        bloom=0.34, bloom_radius=0.52, motif=motif_ghost_fade),
    "golden_radiance": AuraSpec(
        "golden_radiance", _c("pale_gold", "gold", "amber"),
        bloom=0.52, bloom_radius=0.55, motif=motif_radiance,
        notes="legendary — the loudest plate in the set"),
    "chia_bloom": AuraSpec(
        "chia_bloom", _c("bright_green", "chia_green", "gold"),
        bloom=0.48, motif=motif_chia_bloom, notes="mythic, Chia-coded"),
    "corruption_static": AuraSpec(
        "corruption_static", _c("amethyst", "deep_violet", "ink_black"),
        bloom=0.30, ink_color="ink_black", motif=motif_corruption,
        notes="mythic — glitch rendered as ink displacement, not RGB split"),
}


# ------------------------------------------------------------------ render


def face_guard_mask(size: int, keep: float) -> np.ndarray:
    """Multiplier that pulls alpha down over the head so features survive.

    The aura is the last layer composited; without this it paints straight over
    the eyes and mouth that carry the character's expression.
    """
    cx, cy = FOCUS[0] * size, FOCUS[1] * size
    rx, ry = FACE_GUARD[0] * size, FACE_GUARD[1] * size
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.hypot((xs - cx) / rx, (ys - cy) / ry)
    return (keep + (1.0 - keep) * smoothstep(0.55, 1.15, d)).astype(np.float32)


def render(trait_key: str, size: int = 2048) -> Canvas:
    """Render one aura plate. Deterministic in ``trait_key``."""
    spec = AURA_SPECS[trait_key]
    rng = rng_for(f"aura/{trait_key}/v1")
    canvas = Canvas(size)
    ctx = AuraCtx(spec=spec, size=size, rng=rng, canvas=canvas)

    # A ring rather than a disc: light the figure's edge, leave its centre.
    halo = ctx.ring(TORSO, spec.bloom_radius * 0.62, spec.bloom_radius * 0.34)
    grain = 0.80 + 0.20 * value_noise(size, size, 6, rng)
    ctx.paint(halo * spec.bloom * grain, spec.colors[0])
    ctx.paint(ctx.radial(TORSO, spec.bloom_radius * 1.35, falloff=3.2)
              * spec.bloom * 0.22, spec.colors[-1])

    if spec.motif is not None:
        spec.motif(ctx)

    canvas.multiply_alpha(face_guard_mask(size, spec.guard))
    canvas.multiply_alpha(MAX_ALPHA)
    return canvas


def all_keys() -> list[str]:
    return list(AURA_SPECS)
