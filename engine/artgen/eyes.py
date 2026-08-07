# SPDX-License-Identifier: MIT
"""Eyes layer (z-order 8) — the pupil, and whatever the expression needs.

Authored against ``rig.CANONICAL``: eye centre (0.520, 0.145), eye width 0.062.
``render_engine._place_face`` scales by that width, translates onto each body's
own eye, and mirrors where the body faces the other way.

What this layer draws — and what it deliberately does not
--------------------------------------------------------
The body plates keep their **iris, sclera, eyelid and socket**, all hand-drawn.
Only their pupil is removed (``artgen.repair.blank_pupil``). So this layer
supplies the pupil and, where an expression demands it, a lid or an accent —
nothing else.

The previous version drew a complete opaque eyeball over the top. It read as a
decal: a constructed shape sitting on a hand-drawn face, and no amount of
correcting its placement or scale fixed that, because the problem was that it
was replacing better art than it could produce. Drawing only the part that
actually varies between traits keeps the character's own eye and still lets
sixteen traits change it.

Sizing follows from the blanking. ``blank_pupil`` clears a disc of radius
``0.34 * eye_w``; anything drawn beyond that lands on iris the artist drew, so
``PUPIL_R`` stays inside it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field as dc_field
from typing import Callable, Sequence

import numpy as np

from . import ink
from .core import Canvas, blur, load_palette, master_scale, rng_for

PAL = load_palette()

EYE = (0.520, 0.145)
"""Eye centre in canonical rig space — must equal ``rig.CANONICAL`` eye."""

EYE_W = 0.062
"""Canonical eye width — must equal ``rig.CANONICAL.eye_w``.

The compositor scales by ``anchor.eye_w / canonical.eye_w``, so art drawn
against a different width lands at the wrong size on every body.
"""

PUPIL_R = 0.0165
"""Base pupil radius, canonical canvas units.

Bounded by the blanked disc (``0.34 * EYE_W`` = 0.0211): a pupil larger than
the cleared area would overlap iris the artist drew.
"""

LID_INK = "ink_black"
MAX_ALPHA = 1.0


def _c(name: str) -> tuple[int, int, int]:
    return PAL[name]


@dataclass(frozen=True)
class EyeSpec:
    key: str
    pupil_scale: float = 1.0
    """Pupil size relative to ``PUPIL_R``."""
    aspect: float = 1.10
    """Pupil height / width. Above 1 gives the vertical slit of the reference."""
    gaze: tuple[float, float] = (0.0, 0.0)
    """Pupil offset from the eye centre, in pupil radii."""
    colour: str = "ink_black"
    highlight: float = 0.55
    """Size of the catchlight relative to the pupil; 0 omits it."""
    lid: float = 0.0
    """Fraction of the eye the lid covers, from the top. 1.0 is shut."""
    brow: float = 0.0
    """Brow stroke angle in radians; 0 omits it."""
    shape: Callable[["EyeCtx"], np.ndarray] | None = None
    """Custom pupil silhouette, replacing the default ellipse."""
    accent: Callable[["EyeCtx"], None] | None = None
    """Drawn after the pupil; may reach outside the eye (tears, a beam)."""
    notes: str = ""
    extras: dict = dc_field(default_factory=dict)


@dataclass
class EyeCtx:
    spec: EyeSpec
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

    def mask(self) -> np.ndarray:
        return np.zeros((self.size, self.size), dtype=np.float32)

    def paint(self, mask: np.ndarray, color: Sequence[float] | np.ndarray,
              alpha_scale: float = 1.0) -> None:
        rgb = (np.broadcast_to(np.asarray(color, dtype=np.float32),
                               (self.size, self.size, 3))
               if np.ndim(color) == 1 else color)
        self.canvas.over(rgb, np.clip(mask * alpha_scale, 0.0, 1.0))

    # -- canonical geometry, in pixels -----------------------------------
    @property
    def cx(self) -> float:
        return EYE[0] * self.size

    @property
    def cy(self) -> float:
        return EYE[1] * self.size

    @property
    def eye_r(self) -> float:
        """Half the canonical eye width — the extent a lid must cover."""
        return EYE_W * 0.5 * self.size

    @property
    def r(self) -> float:
        return PUPIL_R * self.size * self.spec.pupil_scale

    @property
    def gx(self) -> float:
        return self.cx + self.spec.gaze[0] * self.r

    @property
    def gy(self) -> float:
        return self.cy + self.spec.gaze[1] * self.r

    def ellipse(self, cx: float, cy: float, rx: float, ry: float,
                n: int = 64) -> list[tuple[float, float]]:
        return [(cx + math.cos(a) * rx, cy + math.sin(a) * ry)
                for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]

    def disc(self, cx: float, cy: float, rx: float,
             ry: float | None = None) -> np.ndarray:
        m = self.mask()
        ink.fill_poly(m, self.ellipse(cx, cy, rx, ry if ry is not None else rx), 1.0)
        return m


# ------------------------------------------------------------ pupil shapes


def shape_heart(ctx: EyeCtx) -> np.ndarray:
    r = ctx.r * 1.15
    cx, cy = ctx.gx, ctx.gy + r * 0.12
    pts = []
    for t in np.linspace(0, 2 * math.pi, 90):
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t)
              - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * r / 17.0, cy + y * r / 17.0))
    m = ctx.mask()
    ink.fill_poly(m, pts, 1.0)
    return m


def shape_star(ctx: EyeCtx) -> np.ndarray:
    r = ctx.r * 1.25
    cx, cy = ctx.gx, ctx.gy
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.44
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    m = ctx.mask()
    ink.fill_poly(m, pts, 1.0)
    return m


def shape_diamond(ctx: EyeCtx) -> np.ndarray:
    r = ctx.r * 1.25
    cx, cy = ctx.gx, ctx.gy
    m = ctx.mask()
    ink.fill_poly(m, [(cx, cy - r), (cx + r * 0.72, cy - r * 0.18),
                      (cx, cy + r), (cx - r * 0.72, cy - r * 0.18)], 1.0)
    return m


def shape_cross(ctx: EyeCtx) -> np.ndarray:
    """A bold X — `dead` in ink, `xch` in Chia green."""
    r = ctx.r * 1.35
    cx, cy = ctx.gx, ctx.gy
    w = max(1.0, ctx.px(13.0) * ctx.spec.pupil_scale)
    m = ctx.mask()
    for d in (-1, 1):
        ink.calligraphic_stroke(m, [(cx - d * r, cy - r), (cx + d * r, cy + r)],
                                w, w, taper=1.0)
    return m


def shape_sigil(ctx: EyeCtx) -> np.ndarray:
    r = ctx.r * 1.3
    cx, cy = ctx.gx, ctx.gy
    m = ctx.mask()
    ink.polyline(m, ctx.ellipse(cx, cy, r, r, 48), max(1.0, ctx.px(4.5)), 1.0,
                 closed=True)
    pent = [(cx + math.cos(-math.pi / 2 + i * 2 * math.pi / 5) * r * 0.86,
             cy + math.sin(-math.pi / 2 + i * 2 * math.pi / 5) * r * 0.86)
            for i in range(5)]
    order = [0, 2, 4, 1, 3, 0]
    for a, b in zip(order, order[1:]):
        ink.polyline(m, [pent[a], pent[b]], max(1.0, ctx.px(4.0)), 1.0)
    return m


def shape_finger(ctx: EyeCtx) -> np.ndarray:
    """Proportions well past anatomy: at this size the read is one tall shape
    rising out of one wide one."""
    r = ctx.r * 1.15
    cx, cy = ctx.gx, ctx.gy + r * 0.28
    m = ctx.mask()
    ink.fill_poly(m, [(cx - r * 0.72, cy - r * 0.02), (cx + r * 0.72, cy - r * 0.02),
                      (cx + r * 0.58, cy + r * 0.80), (cx - r * 0.58, cy + r * 0.80)],
                  1.0)
    ink.fill_poly(m, [(cx - r * 0.20, cy - r * 1.50), (cx + r * 0.20, cy - r * 1.50),
                      (cx + r * 0.20, cy + r * 0.10), (cx - r * 0.20, cy + r * 0.10)],
                  1.0)
    return m


# ---------------------------------------------------------------- accents


def accent_tears(ctx: EyeCtx) -> None:
    """Tears fall below the eye, deliberately outside it."""
    rng = ctx.rng
    m = ctx.mask()
    for i in range(3):
        x = ctx.cx + ctx.eye_r * float(rng.uniform(-0.55, 0.30))
        y0 = ctx.cy + ctx.eye_r * 0.80
        drop = ctx.eye_r * float(rng.uniform(1.1, 2.6)) * (1.0 + 0.3 * i)
        rad = max(1.5, ctx.px(9.0) * float(rng.uniform(0.8, 1.3)))
        pts = [(x, y0)]
        for t in np.linspace(0.0, 1.0, 18):
            pts.append((x + math.sin(t * math.pi) * rad, y0 + drop * t))
        for t in np.linspace(1.0, 0.0, 18):
            pts.append((x - math.sin(t * math.pi) * rad, y0 + drop * t))
        ink.fill_poly(m, pts, 1.0)
        ink.fill_poly(m, ctx.ellipse(x, y0 + drop, rad, rad * 1.05), 1.0)
    ctx.paint(m, _c("pale_blue"), 0.92)
    ctx.paint(ctx.soft(m, 5.0), _c("steel_blue"), 0.45)


def accent_laser(ctx: EyeCtx) -> None:
    """A hot core and a beam leaving the eye."""
    core = ctx.disc(ctx.gx, ctx.gy, ctx.r * 0.85)
    ctx.paint(core, _c("bone_white"), 1.0)
    ctx.paint(ctx.soft(core, 8.0), _c("coral"), 0.85)
    beam = ctx.mask()
    length = ctx.size * 0.13
    ink.fill_poly(beam, [(ctx.cx, ctx.cy - ctx.r * 0.5),
                         (ctx.cx, ctx.cy + ctx.r * 0.5),
                         (ctx.cx + length, ctx.cy + ctx.r * 1.5),
                         (ctx.cx + length, ctx.cy - ctx.r * 1.5)], 1.0)
    ctx.paint(ctx.soft(beam, 12.0) * 0.9, _c("crimson"), 0.60)
    ctx.paint(ctx.soft(beam, 3.5) * 0.8, _c("bone_white"), 0.55)


def accent_glow(ctx: EyeCtx) -> None:
    """A soft aura around a magical pupil — wizard, xch, diamond, stars."""
    colour = ctx.spec.extras.get("glow", "lavender")
    m = ctx.disc(ctx.gx, ctx.gy, ctx.r * 1.5)
    ctx.paint(ctx.soft(m, 10.0) * 0.7, _c(colour), 0.45)


# --------------------------------------------------------------- assembly


def _draw_pupil(ctx: EyeCtx) -> None:
    spec = ctx.spec
    if spec.lid >= 0.99:
        return                                  # a shut eye has no pupil
    m = (spec.shape(ctx) if spec.shape is not None
         else ctx.disc(ctx.gx, ctx.gy, ctx.r, ctx.r * spec.aspect))
    ctx.paint(m, _c(spec.colour), 1.0)
    if spec.highlight > 0.02:
        h = ctx.disc(ctx.gx - ctx.r * 0.34, ctx.gy - ctx.r * 0.42,
                     ctx.r * 0.34 * spec.highlight,
                     ctx.r * 0.30 * spec.highlight)
        ctx.paint(h, _c("bone_white"), 0.95)


def _draw_lid(ctx: EyeCtx) -> None:
    """Close the eye from the top by the spec's fraction.

    The lid cannot be skin-coloured — this sprite has no idea what colour the
    body underneath is, and there are eight colourways. It is drawn instead in
    the character's own idiom: a heavy ink lid with lashes, which reads as a
    closed eye over any skin tone.
    """
    spec = ctx.spec
    if spec.lid <= 0.01:
        return
    rx, ry = ctx.eye_r * 1.02, ctx.eye_r * 0.82
    top = ctx.cy - ry
    edge = top + 2 * ry * spec.lid

    m = ctx.mask()
    upper = [(ctx.cx - rx + 2 * rx * t,
              ctx.cy - ry * math.sin(math.pi * t) ** 0.7)
             for t in np.linspace(0.0, 1.0, 40)]
    lower = [(ctx.cx + rx - 2 * rx * t,
              edge + ry * 0.22 * math.sin(math.pi * t))
             for t in np.linspace(0.0, 1.0, 40)]
    ink.fill_poly(m, upper + lower, 1.0)
    # A shut lid has to hide the eye, so it goes nearly opaque. A partial one
    # should not: at full strength it reads as a grey slab laid over the top of
    # the eye rather than a lid coming down, and the ink rim below does most of
    # the work anyway.
    ctx.paint(m, _c("slate_gray"), 0.30 + 0.65 * spec.lid)

    rim = ctx.mask()
    ink.calligraphic_stroke(rim, lower[::-1], max(1.2, ctx.px(9.0)),
                            max(1.0, ctx.px(4.0)), taper=0.8)
    if spec.lid >= 0.99:
        for i in range(5):
            t = 0.18 + 0.16 * i
            x = ctx.cx - rx + 2 * rx * t
            ink.calligraphic_stroke(
                rim, [(x, edge + ry * 0.14), (x - rx * 0.10, edge + ry * 0.52)],
                max(1.0, ctx.px(5.0)), max(0.8, ctx.px(1.8)), taper=1.2)
    ctx.paint(rim, _c(LID_INK), 1.0)


def _draw_brow(ctx: EyeCtx) -> None:
    if ctx.spec.brow == 0.0:
        return
    rx = ctx.eye_r
    by = ctx.cy - ctx.eye_r * 1.45
    tilt = math.tan(ctx.spec.brow) * rx
    m = ctx.mask()
    ink.calligraphic_stroke(
        m, ink.catmull_rom([(ctx.cx - rx * 1.05, by + tilt),
                            (ctx.cx, by - ctx.eye_r * 0.22),
                            (ctx.cx + rx * 1.0, by - tilt * 0.4)]),
        max(1.4, ctx.px(11.0)), max(1.0, ctx.px(4.0)), taper=0.9)
    ctx.paint(m, _c(LID_INK), 0.95)


# ------------------------------------------------------------------ specs

EYE_SPECS: dict[str, EyeSpec] = {
    "normal": EyeSpec("normal"),
    "sleepy": EyeSpec("sleepy", lid=0.52, gaze=(0.0, 0.30), pupil_scale=0.92,
                      notes="lid at half mast"),
    "closed": EyeSpec("closed", lid=1.0, highlight=0.0,
                      notes="the only trait with no pupil"),
    "determined": EyeSpec("determined", lid=0.20, brow=0.48, gaze=(0.22, 0.0),
                          pupil_scale=1.05, aspect=1.25),
    "scared": EyeSpec("scared", pupil_scale=0.58, brow=-0.30, aspect=1.0,
                      notes="a small pupil leaves the artist's iris showing"),
    "crying": EyeSpec("crying", gaze=(0.0, 0.18), accent=accent_tears),
    "hopeful": EyeSpec("hopeful", pupil_scale=1.12, gaze=(0.06, -0.26),
                       brow=-0.18, highlight=0.85, aspect=1.0),
    "looking_to_horizon": EyeSpec("looking_to_horizon", gaze=(0.85, 0.0),
                                  aspect=1.2),
    "dead": EyeSpec("dead", shape=shape_cross, highlight=0.0),
    "heart": EyeSpec("heart", shape=shape_heart, colour="crimson",
                     highlight=0.45),
    "laser": EyeSpec("laser", accent=accent_laser, highlight=0.0,
                     colour="crimson"),
    "middle_finger_pupils": EyeSpec("middle_finger_pupils", shape=shape_finger,
                                    highlight=0.0, notes="meme tier"),
    "pixel_stars": EyeSpec("pixel_stars", shape=shape_star, colour="pale_gold",
                           highlight=0.0, accent=accent_glow,
                           extras={"glow": "sand"}),
    "wizard": EyeSpec("wizard", shape=shape_sigil, colour="amethyst",
                      highlight=0.0, accent=accent_glow,
                      extras={"glow": "lavender"}),
    "diamond": EyeSpec("diamond", shape=shape_diamond, colour="pale_blue",
                       highlight=0.7, accent=accent_glow,
                       extras={"glow": "steel_blue"}, notes="legendary"),
    "xch": EyeSpec("xch", shape=shape_cross, colour="bright_green",
                   highlight=0.0, accent=accent_glow,
                   extras={"glow": "chia_green"},
                   notes="legendary — the Chia mark"),
}


# ------------------------------------------------------------------ render


def render(trait_key: str, size: int = 2048) -> Canvas:
    """Render one eye plate in canonical rig space. Deterministic."""
    spec = EYE_SPECS[trait_key]
    rng = rng_for(f"eyes/{trait_key}/v2")
    canvas = Canvas(size)
    ctx = EyeCtx(spec=spec, size=size, rng=rng, canvas=canvas)

    _draw_pupil(ctx)
    if spec.accent is not None:
        spec.accent(ctx)
    _draw_lid(ctx)
    _draw_brow(ctx)

    canvas.multiply_alpha(MAX_ALPHA)
    return canvas


def all_keys() -> list[str]:
    return list(EYE_SPECS)
