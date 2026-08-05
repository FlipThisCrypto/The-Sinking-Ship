# SPDX-License-Identifier: MIT
"""Eyes layer (z-order 8) — the character's expression.

Authored against ``rig.CANONICAL``: eye centre at (0.520, 0.145), head height
0.190. ``render_engine._place_face`` scales, translates and (where the body
faces the other way) mirrors this onto each body's actual head, so everything
here is drawn once in canonical head space.

Two constraints shape every plate:

**One eye, not two.** ``docs/art-reference/ART-DIRECTION.md`` names *a single
large expressive eye in profile* as the species cue, and the body plates
disagree about how many eyes are visible — some are profile, some
three-quarter. A single eye on the rig anchor reads correctly on all of them; a
pair would put an eye on the snout of every profile body.

**The eye must occlude, not overlay.** The body art already has an eye drawn at
this spot. A transparent pupil decal would show the original eye through it —
"closed" would render an open eye with a lid floating over it. So every trait
lays down an opaque bone-white eye body first and then inks the state onto it.
That is also the medium's own logic: ink on paper, with the paper showing
through as the white of the eye.
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

EYE_W = 0.031
"""Half-width of the eye opening, so the drawn eye is ``rig.CANONICAL.eye_w``.

This must equal half of the rig's canonical eye width. The compositor scales
each plate by ``anchor.eye_w / canonical.eye_w``, so if the art here is drawn at
a different size than the rig claims, every eye lands at the wrong scale —
which is exactly what happened when this layer scaled by head height instead:
eye-to-head ratio varies by more than 2x across the body plates, so head-based
scaling made the eye far too large on small-eyed bodies like ``green_standing``
(0.037) and too small on ``blue_back_turned`` (0.090).
"""

EYE_H = 0.026
LID_INK = "ink_black"
MAX_ALPHA = 1.0


def _c(name: str) -> tuple[int, int, int]:
    return PAL[name]


@dataclass(frozen=True)
class EyeSpec:
    key: str
    iris: str = "sea_blue"
    """Iris colour name from the master palette."""
    open_amount: float = 1.0
    """1.0 fully open, 0.0 shut. Drives the lid."""
    pupil: float = 0.34
    """Pupil radius as a fraction of the iris radius."""
    gaze: tuple[float, float] = (0.0, 0.0)
    """Pupil offset within the iris, in iris radii."""
    brow: float = 0.0
    """Brow angle in radians; positive lowers the inner end (a scowl)."""
    line_alpha: float = 1.0
    motif: Callable[["EyeCtx"], None] | None = None
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

    # -- canonical head geometry, in pixels -------------------------------
    @property
    def cx(self) -> float:
        return EYE[0] * self.size

    @property
    def cy(self) -> float:
        return EYE[1] * self.size

    @property
    def rx(self) -> float:
        return EYE_W * self.size

    @property
    def ry(self) -> float:
        return EYE_H * self.size

    @property
    def iris_r(self) -> float:
        return self.ry * 0.86

    def ellipse(self, cx: float, cy: float, rx: float, ry: float,
                n: int = 72) -> list[tuple[float, float]]:
        return [(cx + math.cos(a) * rx, cy + math.sin(a) * ry)
                for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]

    def disc(self, cx: float, cy: float, r: float, ry: float | None = None
             ) -> np.ndarray:
        m = self.mask()
        ink.fill_poly(m, self.ellipse(cx, cy, r, ry if ry is not None else r), 1.0)
        return m


# ------------------------------------------------------------- eye assembly


def _almond(ctx: EyeCtx, open_amount: float) -> list[tuple[float, float]]:
    """The eye opening: a lens between an upper lid arc and a lower lid arc."""
    cx, cy, rx, ry = ctx.cx, ctx.cy, ctx.rx, ctx.ry
    top = ry * max(0.06, open_amount) * 0.92
    bottom = ry * max(0.06, 0.55 + 0.45 * open_amount) * 0.72
    upper = [(cx - rx + 2 * rx * t,
              cy - top * math.sin(math.pi * t) ** 0.72)
             for t in np.linspace(0.0, 1.0, 48)]
    lower = [(cx + rx - 2 * rx * t,
              cy + bottom * math.sin(math.pi * t) ** 0.9)
             for t in np.linspace(0.0, 1.0, 48)]
    return upper + lower


def _draw_eyeball(ctx: EyeCtx) -> np.ndarray:
    """Opaque eye body + iris + pupil. Returns the eye-*opening* for clipping.

    Two shapes, and conflating them is a bug this layer had:

    ``cover``
        the eye region at full extent, always. This is what occludes the eye
        already drawn on the body, so it must not shrink when the lid lowers —
        otherwise a shut eye leaves the body's open eye visible around a thin
        sliver of lid, which is precisely the artefact this layer exists to
        avoid.
    ``opening``
        the lens actually visible at this ``open_amount``, used to clip the
        iris, pupil and any motif.
    """
    spec = ctx.spec
    cover = ctx.mask()
    ink.fill_poly(cover, _almond(ctx, 1.0), 1.0)
    ctx.paint(cover, _c("bone_white"), 1.0)

    opening = ctx.mask()
    ink.fill_poly(opening, _almond(ctx, spec.open_amount), 1.0)

    if spec.open_amount < 0.12:
        return opening

    gx, gy = spec.gaze
    ix = ctx.cx + gx * ctx.iris_r
    iy = ctx.cy + gy * ctx.iris_r * 0.7
    iris = np.minimum(ctx.disc(ix, iy, ctx.iris_r), opening)
    ctx.paint(iris, _c(spec.iris), 1.0)
    # a darker rim reads as depth and keeps the iris from floating
    rim = np.minimum(
        np.clip(ctx.disc(ix, iy, ctx.iris_r)
                - ctx.disc(ix, iy, ctx.iris_r * 0.80), 0, 1), opening)
    ctx.paint(rim, _c("deep_ink"), 0.55)

    if spec.motif is None or ctx.spec.extras.get("keep_pupil", True):
        pupil = np.minimum(ctx.disc(ix, iy, ctx.iris_r * spec.pupil), opening)
        ctx.paint(pupil, _c("ink_black"), 1.0)
    return opening


def _draw_lids(ctx: EyeCtx, opening: np.ndarray) -> None:
    """Lash line, lower lid and brow — the ink that gives the eye its mood."""
    spec = ctx.spec
    m = ctx.mask()
    cx, cy, rx, ry = ctx.cx, ctx.cy, ctx.rx, ctx.ry

    lens = _almond(ctx, spec.open_amount)
    upper = lens[:48]
    lower = lens[48:]
    ink.calligraphic_stroke(m, upper, ctx.px(11.0), ctx.px(5.0), taper=0.7)
    ink.calligraphic_stroke(m, lower, ctx.px(6.0), ctx.px(3.0), taper=0.8)

    if spec.brow != 0.0:
        by = cy - ry * 1.85
        tilt = math.tan(spec.brow) * rx
        ink.calligraphic_stroke(
            m, ink.catmull_rom([(cx - rx * 1.1, by + tilt),
                                (cx, by - ry * 0.30),
                                (cx + rx * 1.05, by - tilt * 0.4)]),
            ctx.px(13.0), ctx.px(5.0), taper=0.9)

    if spec.open_amount < 0.12:
        # A shut eye is read from its lid line, so make that the heaviest mark
        # on the plate, with lashes hanging off it.
        ink.calligraphic_stroke(
            m, ink.catmull_rom([(cx - rx * 1.02, cy - ry * 0.10),
                                (cx, cy + ry * 0.26),
                                (cx + rx * 1.02, cy - ry * 0.06)]),
            ctx.px(17.0), ctx.px(7.0), taper=0.8)
        for i in range(5):
            t = 0.16 + 0.17 * i
            x = cx - rx + 2 * rx * t
            ink.calligraphic_stroke(
                m, [(x, cy + ry * 0.20), (x - rx * 0.12, cy + ry * 0.62)],
                ctx.px(8.0), ctx.px(2.5), taper=1.2)

    ctx.paint(m, _c(LID_INK), spec.line_alpha)

    if spec.open_amount >= 0.12:
        hl = np.minimum(
            ctx.disc(cx - rx * 0.30, cy - ry * 0.34, ry * 0.22, ry * 0.17), opening)
        ctx.paint(hl, _c("bone_white"), 0.95)


# ------------------------------------------------------------------ motifs


def _pupil_shape(ctx: EyeCtx, points: list[tuple[float, float]], opening,
                 color: str = "ink_black") -> None:
    m = ctx.mask()
    ink.fill_poly(m, points, 1.0)
    ctx.paint(np.minimum(m, opening), _c(color), 1.0)


def motif_heart(ctx: EyeCtx, opening) -> None:
    r = ctx.iris_r * 0.86
    cx, cy = ctx.cx, ctx.cy + r * 0.12
    pts = []
    for t in np.linspace(0, 2 * math.pi, 90):
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t)
              - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * r / 17.0, cy + y * r / 17.0))
    _pupil_shape(ctx, pts, opening, "crimson")


def motif_star(ctx: EyeCtx, opening) -> None:
    """A five-point star pupil with blocky studs — the pixel-art wink.

    The first attempt built the star from grid cells and came out a plus sign;
    a clean star polygon plus a few square studs reads far better at eye scale.
    """
    r = ctx.iris_r * 1.0
    cx, cy = ctx.cx, ctx.cy
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.44
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    _pupil_shape(ctx, pts, opening, "pale_gold")
    studs = ctx.mask()
    step = r * 0.30
    for gx, gy in ((-2.0, -1.4), (2.0, -1.4), (0.0, 1.8)):
        x, y = cx + gx * step, cy + gy * step
        ink.fill_poly(studs, [(x - step * 0.4, y - step * 0.4),
                              (x + step * 0.4, y - step * 0.4),
                              (x + step * 0.4, y + step * 0.4),
                              (x - step * 0.4, y + step * 0.4)], 1.0)
    ctx.paint(np.minimum(studs, opening), _c("sand"), 0.95)


def motif_diamond(ctx: EyeCtx, opening) -> None:
    r = ctx.iris_r * 0.95
    cx, cy = ctx.cx, ctx.cy
    body = [(cx, cy - r), (cx + r * 0.78, cy - r * 0.18),
            (cx, cy + r), (cx - r * 0.78, cy - r * 0.18)]
    _pupil_shape(ctx, body, opening, "pale_blue")
    facets = ctx.mask()
    ink.polyline(facets, body, ctx.px(4.0), 1.0, closed=True)
    ink.polyline(facets, [(cx - r * 0.78, cy - r * 0.18),
                          (cx + r * 0.78, cy - r * 0.18)], ctx.px(3.0), 0.9)
    ink.polyline(facets, [(cx, cy - r), (cx, cy + r)], ctx.px(3.0), 0.7)
    ctx.paint(np.minimum(facets, opening), _c("bone_white"), 0.95)


def motif_xch(ctx: EyeCtx, opening) -> None:
    """The Chia X as the pupil — the Chia-coded legendary.

    Mark only, no leaf: overlaying both turned the pupil into a green blob at
    eye scale. One clean bold X on a deep iris reads instantly.
    """
    r = ctx.iris_r * 0.95
    cx, cy = ctx.cx, ctx.cy
    m = ctx.mask()
    for d in (-1, 1):
        ink.calligraphic_stroke(m, [(cx - d * r * 0.78, cy - r * 0.78),
                                    (cx + d * r * 0.78, cy + r * 0.78)],
                                ctx.px(15.0), ctx.px(15.0), taper=1.0)
    ctx.paint(np.minimum(m, opening), _c("bright_green"), 1.0)
    ctx.paint(np.minimum(ctx.soft(m, 7.0), opening), _c("chia_green"), 0.5)


def motif_wizard(ctx: EyeCtx, opening) -> None:
    r = ctx.iris_r * 0.95
    cx, cy = ctx.cx, ctx.cy
    m = ctx.mask()
    for k in range(2):
        ink.polyline(m, ctx.ellipse(cx, cy, r * (1.0 - k * 0.28),
                                    r * (1.0 - k * 0.28), 60),
                     ctx.px(4.0), 1.0, closed=True)
    pent = [(cx + math.cos(-math.pi / 2 + i * 2 * math.pi / 5) * r * 0.82,
             cy + math.sin(-math.pi / 2 + i * 2 * math.pi / 5) * r * 0.82)
            for i in range(5)]
    order = [0, 2, 4, 1, 3, 0]
    for a, b in zip(order, order[1:]):
        ink.polyline(m, [pent[a], pent[b]], ctx.px(3.4), 0.95)
    ctx.paint(np.minimum(m, opening), _c("amethyst"), 1.0)
    ctx.paint(np.minimum(ctx.soft(m, 9.0), opening), _c("lavender"), 0.55)


def motif_laser(ctx: EyeCtx, opening) -> None:
    """A hot pupil and a short beam leaving the eye."""
    r = ctx.iris_r
    cx, cy = ctx.cx, ctx.cy
    core = np.minimum(ctx.disc(cx, cy, r * 0.55), opening)
    ctx.paint(core, _c("bone_white"), 1.0)
    ctx.paint(np.minimum(ctx.soft(core, 10.0), opening), _c("coral"), 0.8)
    beam = ctx.mask()
    length = ctx.size * 0.16
    ink.fill_poly(beam, [(cx, cy - r * 0.34), (cx, cy + r * 0.34),
                         (cx + length, cy + r * 0.9), (cx + length, cy - r * 0.9)],
                  1.0)
    ctx.paint(ctx.soft(beam, 14.0) * 0.9, _c("crimson"), 0.62)
    ctx.paint(ctx.soft(beam, 4.0) * 0.8, _c("bone_white"), 0.55)


def motif_dead(ctx: EyeCtx, opening) -> None:
    r = ctx.iris_r * 1.15
    cx, cy = ctx.cx, ctx.cy
    m = ctx.mask()
    for d in (-1, 1):
        ink.calligraphic_stroke(m, [(cx - d * r, cy - r), (cx + d * r, cy + r)],
                                ctx.px(13.0), ctx.px(9.0), taper=1.0)
    ctx.paint(np.minimum(m, opening), _c("ink_black"), 1.0)


def motif_finger(ctx: EyeCtx, opening) -> None:
    """A raised middle finger for a pupil — the meme tier.

    Proportions are exaggerated well past anatomy: at this size the read comes
    from one tall narrow shape rising out of one wide short shape, with a gap
    of sclera around it.
    """
    r = ctx.iris_r * 0.95
    cx, cy = ctx.cx, ctx.cy + r * 0.30
    m = ctx.mask()
    ink.fill_poly(m, [(cx - r * 0.70, cy - r * 0.02), (cx + r * 0.70, cy - r * 0.02),
                      (cx + r * 0.58, cy + r * 0.82), (cx - r * 0.58, cy + r * 0.82)],
                  1.0)
    ink.fill_poly(m, [(cx - r * 0.19, cy - r * 1.55), (cx + r * 0.19, cy - r * 1.55),
                      (cx + r * 0.19, cy + r * 0.10), (cx - r * 0.19, cy + r * 0.10)],
                  1.0)
    ctx.paint(np.minimum(m, opening), _c("ink_black"), 1.0)
    gaps = ctx.mask()
    for d in (-1, 1):
        ink.polyline(gaps, [(cx + d * r * 0.36, cy + r * 0.16),
                            (cx + d * r * 0.36, cy + r * 0.74)], ctx.px(4.0), 1.0)
    ctx.paint(np.minimum(gaps, opening), _c("bone_white"), 0.9)


def motif_tears(ctx: EyeCtx, opening) -> None:
    """Tears fall outside the eye opening, so they are drawn unclipped."""
    s, rng = ctx.size, ctx.rng
    m = ctx.mask()
    for i in range(3):
        x = ctx.cx + ctx.rx * float(rng.uniform(-0.55, 0.35))
        y0 = ctx.cy + ctx.ry * 0.85
        drop = s * float(rng.uniform(0.035, 0.085)) * (1.0 + 0.35 * i)
        r = ctx.px(float(rng.uniform(11, 18)))
        # a teardrop: a point at the top widening into a round belly
        tip = (x, y0)
        belly = (x - r * 0.2, y0 + drop)
        pts = [tip]
        for t in np.linspace(0.0, 1.0, 22):
            pts.append((belly[0] + math.sin(t * math.pi) * r,
                        y0 + drop * t))
        for t in np.linspace(1.0, 0.0, 22):
            pts.append((belly[0] - math.sin(t * math.pi) * r,
                        y0 + drop * t))
        ink.fill_poly(m, pts, 1.0)
        ink.fill_poly(m, ctx.ellipse(belly[0], belly[1], r, r * 1.05), 1.0)
    ctx.paint(m, _c("pale_blue"), 0.92)
    ctx.paint(ctx.soft(m, 6.0), _c("steel_blue"), 0.5)


# -------------------------------------------------------------------- specs

EYE_SPECS: dict[str, EyeSpec] = {
    "normal": EyeSpec("normal", iris="sea_blue"),
    "sleepy": EyeSpec("sleepy", iris="sea_blue", open_amount=0.42, pupil=0.30,
                      gaze=(0.0, 0.18), notes="lid at half mast"),
    "closed": EyeSpec("closed", open_amount=0.0,
                      notes="a shut lid must still occlude the eye drawn on the body"),
    "determined": EyeSpec("determined", iris="navy", open_amount=0.72, pupil=0.42,
                          brow=0.42, gaze=(0.10, 0.0)),
    "scared": EyeSpec("scared", iris="steel_blue", open_amount=1.18, pupil=0.20,
                      brow=-0.30, notes="small pupil in a lot of sclera"),
    "crying": EyeSpec("crying", iris="sea_blue", open_amount=0.80, pupil=0.34,
                      gaze=(0.0, 0.12), motif=motif_tears,
                      extras={}),
    "hopeful": EyeSpec("hopeful", iris="pale_blue", open_amount=1.10, pupil=0.30,
                       gaze=(0.05, -0.22), brow=-0.18),
    "looking_to_horizon": EyeSpec("looking_to_horizon", iris="sea_blue",
                                  open_amount=0.88, pupil=0.32, gaze=(0.72, 0.0)),
    "dead": EyeSpec("dead", iris="ash_gray", motif=motif_dead,
                    extras={"keep_pupil": False}),
    "heart": EyeSpec("heart", iris="rose_ash", motif=motif_heart,
                     extras={"keep_pupil": False}),
    "laser": EyeSpec("laser", iris="crimson", open_amount=0.92, motif=motif_laser,
                     extras={"keep_pupil": False}),
    "middle_finger_pupils": EyeSpec("middle_finger_pupils", iris="bone_white",
                                    motif=motif_finger,
                                    extras={"keep_pupil": False},
                                    notes="meme tier"),
    "pixel_stars": EyeSpec("pixel_stars", iris="deep_violet", motif=motif_star,
                           extras={"keep_pupil": False}),
    "wizard": EyeSpec("wizard", iris="deep_violet", motif=motif_wizard,
                      extras={"keep_pupil": False}),
    "diamond": EyeSpec("diamond", iris="steel_blue", motif=motif_diamond,
                       extras={"keep_pupil": False}, notes="legendary"),
    "xch": EyeSpec("xch", iris="deep_teal", motif=motif_xch,
                   extras={"keep_pupil": False},
                   notes="legendary — the Chia mark"),
}


# ------------------------------------------------------------------ render


def render(trait_key: str, size: int = 2048) -> Canvas:
    """Render one eye plate in canonical rig space. Deterministic."""
    spec = EYE_SPECS[trait_key]
    rng = rng_for(f"eyes/{trait_key}/v1")
    canvas = Canvas(size)
    ctx = EyeCtx(spec=spec, size=size, rng=rng, canvas=canvas)

    opening = _draw_eyeball(ctx)
    if spec.motif is not None:
        # Every motif takes the eye opening; ones that spill past it (tears, a
        # laser beam) simply ignore it rather than taking a different signature.
        spec.motif(ctx, opening)
    _draw_lids(ctx, opening)
    canvas.multiply_alpha(MAX_ALPHA)
    return canvas


def all_keys() -> list[str]:
    return list(EYE_SPECS)
