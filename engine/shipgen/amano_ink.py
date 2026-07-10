# SPDX-License-Identifier: MIT
"""Amano-style ink primitives for illustration-profile art.

Matches the visual grammar of ships_amano/ and docs/art-reference/:
  - bone-white ground (transparent layers on white canvas)
  - dense calligraphic polylines, not flat geometric blocks
  - vertical colour ramp along the subject (warm top → navy/ink bottom)
  - selective solid fills (crystals, partial hull shadows)
  - flowing wave ribbons, filigree curls, organic hulls

Used by scripts/gen_placeholder_sprites.py and scripts/style_score.py.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

from PIL import Image, ImageDraw

# Composition fractions shared by all layer renderers
HORIZON = 0.58
DECK_Y = 0.52
HEAD = (0.50, 0.38)
HEAD_R = 0.055

# Vertical gradient ramps (top → mid → bottom). Names map from trait moods.
# Wide separation top→bottom so vertical_ramp metric locks onto ships_amano.
RAMPS: dict[str, list[tuple[int, int, int]]] = {
    "crimson_navy": [(210, 40, 55), (150, 55, 150), (100, 45, 140), (18, 28, 95)],
    "coral_navy": [(235, 110, 95), (200, 80, 120), (120, 55, 140), (14, 24, 85)],
    "gold_navy": [(230, 170, 55), (200, 120, 70), (100, 60, 110), (16, 28, 85)],
    "green_navy": [(55, 190, 115), (40, 140, 120), (35, 80, 130), (14, 26, 85)],
    "violet_navy": [(200, 70, 140), (140, 55, 170), (60, 40, 130), (14, 18, 70)],
    "steel_navy": [(130, 170, 220), (80, 120, 180), (40, 70, 130), (14, 24, 75)],
    "ink": [(90, 100, 130), (40, 50, 100), (16, 18, 45), (10, 10, 18)],
    "bone_ink": [(200, 200, 210), (120, 130, 160), (50, 60, 100), (18, 24, 60)],
    # abyssal: ember/bronze crown → ink floor (ships_amano dark variants)
    "ember_ink": [(210, 90, 40), (140, 60, 80), (50, 40, 90), (12, 14, 35)],
}

MOOD_RAMP = {
    "crimson": "crimson_navy",
    "gold": "gold_navy",
    "green": "green_navy",
    "violet": "violet_navy",
    "blue": "steel_navy",
    "dark": "ink",
    "pale": "bone_ink",
}


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_rgb(c0: Sequence[int], c1: Sequence[int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        round(c0[0] + (c1[0] - c0[0]) * t),
        round(c0[1] + (c1[1] - c0[1]) * t),
        round(c0[2] + (c1[2] - c0[2]) * t),
    )


def ramp_color(stops: Sequence[Sequence[int]], t: float) -> tuple[int, int, int]:
    """t in [0,1] top→bottom along subject."""
    t = max(0.0, min(1.0, t))
    if len(stops) == 1:
        return tuple(stops[0])  # type: ignore[return-value]
    segs = len(stops) - 1
    x = t * segs
    i = min(int(x), segs - 1)
    f = x - i
    return lerp_rgb(stops[i], stops[i + 1], f)


def mood_ramp(mood: str) -> list[tuple[int, int, int]]:
    return RAMPS[MOOD_RAMP.get(mood, "steel_navy")]


def blend(c1, c2, f=0.5):
    return tuple(round(c1[k] + (c2[k] - c1[k]) * f) for k in range(3))


def qbez(p0, p1, p2, n: int = 28) -> list[tuple[float, float]]:
    return [
        (
            (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1],
        )
        for t in (i / n for i in range(n + 1))
    ]


def cbez(p0, p1, p2, p3, n: int = 36) -> list[tuple[float, float]]:
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((
            u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
            u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
        ))
    return out


def catmull(pts: Sequence[tuple[float, float]], n_per: int = 8) -> list[tuple[float, float]]:
    """Smooth through control points (open)."""
    if len(pts) < 2:
        return list(pts)
    pts = list(pts)
    # pad ends
    ext = [pts[0]] + pts + [pts[-1]]
    out: list[tuple[float, float]] = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for j in range(n_per):
            t = j / n_per
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


class InkCanvas:
    """RGBA canvas with gradient-aware ink strokes."""

    def __init__(self, size: int, y0: float | None = None, y1: float | None = None):
        self.size = size
        self.img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.img)
        # vertical ramp domain in pixel space (subject top/bottom)
        self.y0 = (y0 if y0 is not None else 0.12) * size
        self.y1 = (y1 if y1 is not None else 0.90) * size
        self._span = max(1.0, self.y1 - self.y0)

    def t_at(self, y: float) -> float:
        return max(0.0, min(1.0, (y - self.y0) / self._span))

    def color(self, stops, y: float, alpha: int = 255) -> tuple[int, int, int, int]:
        r, g, b = ramp_color(stops, self.t_at(y))
        return (r, g, b, alpha)

    def stroke(
        self,
        pts: Sequence[tuple[float, float]],
        stops,
        width: float,
        alpha: int = 235,
    ) -> None:
        if len(pts) < 2:
            return
        w = max(1, int(round(width)))
        # Per-segment colour by midpoint Y — short segments keep the ramp sharp.
        step = 1
        for i in range(0, len(pts) - 1, step):
            j = min(i + step, len(pts) - 1)
            seg = [pts[i], pts[j]]
            my = (pts[i][1] + pts[j][1]) / 2
            self.draw.line(seg, fill=self.color(stops, my, alpha), width=w, joint="curve")

    def stroke_solid(
        self,
        pts: Sequence[tuple[float, float]],
        color: tuple[int, int, int],
        width: float,
        alpha: int = 235,
    ) -> None:
        if len(pts) < 2:
            return
        self.draw.line(
            list(pts),
            fill=(*color, alpha),
            width=max(1, int(round(width))),
            joint="curve",
        )

    def fill_poly(self, pts, stops, alpha: int = 200, y_sample: float | None = None) -> None:
        if len(pts) < 3:
            return
        y = y_sample if y_sample is not None else sum(p[1] for p in pts) / len(pts)
        self.draw.polygon(list(pts), fill=self.color(stops, y, alpha))

    def fill_poly_solid(self, pts, color, alpha: int = 200) -> None:
        if len(pts) < 3:
            return
        self.draw.polygon(list(pts), fill=(*color, alpha))

    def ellipse(self, box, stops, alpha: int = 220, outline_w: int = 0) -> None:
        y = (box[1] + box[3]) / 2
        fill = self.color(stops, y, alpha)
        if outline_w:
            self.draw.ellipse(box, outline=fill, width=outline_w)
        else:
            self.draw.ellipse(box, fill=fill)


def filigree_curl(
    ink: InkCanvas,
    cx: float,
    cy: float,
    r: float,
    stops,
    turns: float = 1.4,
    width: float = 2.0,
    alpha: int = 200,
    phase: float = 0.0,
    n: int = 48,
) -> None:
    pts = []
    for i in range(n + 1):
        t = i / n
        ang = phase + t * turns * math.tau
        rad = r * (0.15 + 0.85 * t)
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang) * 0.85))
    ink.stroke(pts, stops, width, alpha)


def crystal(
    ink: InkCanvas,
    cx: float,
    cy: float,
    h: float,
    w: float,
    stops,
    tilt: float = 0.0,
    facets: int = 6,
    fill_alpha: int = 180,
) -> None:
    """Faceted gem — solid fill + edge strokes (ships_amano signature motif)."""
    pts = []
    # elongated hexagon-ish crystal pointing up
    top = (cx + math.sin(tilt) * h * 0.2, cy - h)
    bot = (cx - math.sin(tilt) * h * 0.1, cy + h * 0.15)
    left = (cx - w, cy - h * 0.15)
    right = (cx + w, cy - h * 0.15)
    mid_l = (cx - w * 0.55, cy - h * 0.55)
    mid_r = (cx + w * 0.55, cy - h * 0.55)
    poly = [top, mid_r, right, bot, left, mid_l]
    ink.fill_poly(poly, stops, alpha=fill_alpha, y_sample=cy - h * 0.4)
    # facet edges
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ink.stroke([a, b], stops, max(1.5, h * 0.04), 240)
    # internal facet lines
    ink.stroke([top, bot], stops, max(1.0, h * 0.025), 160)
    ink.stroke([mid_l, mid_r], stops, max(1.0, h * 0.02), 140)
    for i in range(facets - 4):
        t = (i + 1) / (facets - 3)
        p = (lerp(left[0], right[0], t), lerp(left[1], right[1], t * 0.3 + 0.7))
        ink.stroke([top, p], stops, max(1.0, h * 0.015), 100)


def wave_ribbons(
    ink: InkCanvas,
    y_base: float,
    amp: float,
    length: float,
    stops,
    strands: int = 5,
    width: float = 2.5,
    phase: float = 0.0,
    x0: float = 0.05,
    x1: float = 0.95,
) -> None:
    """Parallel flowing wave lines — Hokusai/Amano water, not sine fills."""
    s = ink.size
    for k in range(strands):
        pts = []
        yy = y_base + k * amp * 0.45
        for i in range(80):
            t = i / 79
            x = (x0 + (x1 - x0) * t) * s
            y = yy * s + amp * s * (
                0.55 * math.sin(t * math.tau * 1.8 + phase + k * 0.45)
                + 0.28 * math.sin(t * math.tau * 3.4 + phase * 1.3)
                + 0.12 * math.sin(t * math.tau * 5.2 + k)
            )
            lift = math.sin(t * math.pi) ** 0.5
            y -= lift * amp * s * 0.18 * (1 if k % 2 == 0 else -0.35)
            pts.append((x, y))
        smooth = catmull(pts, 5)
        ink.stroke(smooth, stops, width * (1.0 - k * 0.06), 210 - k * 12)
        # twin parallel strand for density
        if k % 2 == 0:
            twin = [(x, y + s * 0.006) for x, y in smooth[::2]]
            ink.stroke(twin, stops, max(1.0, width * 0.55), 140)


def organic_hull(
    ink: InkCanvas,
    cx: float,
    deck_y: float,
    half_w: float,
    depth: float,
    stops,
    bow_lift: float = 0.06,
    fill_alpha: int = 12,
) -> list[tuple[float, float]]:
    """Art-nouveau ship hull — outline + dense plate filigree (line-first)."""
    s = ink.size
    top_l = ((cx - half_w) * s, deck_y * s)
    top_r = ((cx + half_w) * s, deck_y * s)
    bow = ((cx + half_w + 0.04) * s, (deck_y - bow_lift) * s)
    keel_r = ((cx + half_w * 0.75) * s, (deck_y + depth) * s)
    keel_m = (cx * s, (deck_y + depth + 0.02) * s)
    keel_l = ((cx - half_w * 0.75) * s, (deck_y + depth) * s)
    stern = ((cx - half_w - 0.02) * s, (deck_y + 0.01) * s)

    outline = catmull([top_l, stern, keel_l, keel_m, keel_r, bow, top_r, top_l], 14)
    if fill_alpha:
        ink.fill_poly(outline, stops, alpha=fill_alpha, y_sample=(deck_y + depth * 0.5) * s)
    # double outline for weight (ships_amano heavy outer stroke)
    ink.stroke(outline, stops, max(2.8, s * 0.0045), 245)
    ink.stroke(outline, stops, max(1.2, s * 0.002), 160)

    # dense interior plate / filigree lines
    for i in range(10):
        t = 0.08 + i * 0.085
        y = (deck_y + depth * t) * s
        shrink = 0.92 - t * 0.25
        inner = catmull([
            ((cx - half_w * shrink) * s, y + s * 0.004 * math.sin(i)),
            ((cx - half_w * 0.35) * s, y + s * 0.01 * ((i % 3) - 1)),
            ((cx + half_w * 0.15) * s, y - s * 0.008 * ((i % 2) - 0.5)),
            ((cx + half_w * shrink * 0.95) * s, y + s * 0.003 * math.cos(i)),
        ], 8)
        ink.stroke(inner, stops, max(1.0, s * 0.0016), 150)
    # vertical rib strokes
    for i in range(7):
        fx = cx - half_w * 0.75 + i * (half_w * 1.5 / 6)
        rib = catmull([
            (fx * s, deck_y * s),
            ((fx + 0.01 * ((i % 2) - 0.5)) * s, (deck_y + depth * 0.45) * s),
            (fx * s, (deck_y + depth * 0.92) * s),
        ], 6)
        ink.stroke(rib, stops, max(1.0, s * 0.0015), 130)
    return outline


def mast_and_sail(
    ink: InkCanvas,
    mx: float,
    deck_y: float,
    height: float,
    sail_w: float,
    stops,
    billow: float = 0.8,
) -> None:
    s = ink.size
    x = mx * s
    top = (x, (deck_y - height) * s)
    foot = (x, deck_y * s)
    ink.stroke([foot, top], stops, max(1.5, s * 0.0025), 230)
    # billowing sail as cubic
    sail = cbez(
        top,
        (x + sail_w * s * billow, (deck_y - height * 0.85) * s),
        (x + sail_w * s * 0.95, (deck_y - height * 0.35) * s),
        (x + sail_w * s * 0.15, (deck_y - height * 0.12) * s),
        28,
    )
    # sail edge back to mast
    sail_closed = sail + [(x, (deck_y - height * 0.15) * s), top]
    ink.fill_poly(sail_closed, stops, alpha=28, y_sample=(deck_y - height * 0.5) * s)
    ink.stroke(sail, stops, max(1.5, s * 0.0022), 220)
    # yardarm
    ink.stroke(
        [(x - sail_w * s * 0.1, (deck_y - height * 0.92) * s),
         (x + sail_w * s * 0.7, (deck_y - height * 0.88) * s)],
        stops, max(1.0, s * 0.0018), 180,
    )


def gun_turret(ink: InkCanvas, cx: float, cy: float, scale: float, stops, angle: float = -0.2) -> None:
    s = ink.size
    r = scale * s
    ink.ellipse([cx * s - r, cy * s - r * 0.55, cx * s + r, cy * s + r * 0.55], stops, 90)
    ink.ellipse(
        [cx * s - r, cy * s - r * 0.55, cx * s + r, cy * s + r * 0.55],
        stops, 0, outline_w=max(1, int(s * 0.002)),
    )
    # barrels
    for dy in (-0.35, 0.35):
        bx = cx * s + math.cos(angle) * r * 2.4
        by = cy * s + dy * r + math.sin(angle) * r * 2.4
        ink.stroke([(cx * s + r * 0.5, cy * s + dy * r * 0.4), (bx, by)], stops,
                   max(2.0, s * 0.003), 220)


def network_mesh(
    ink: InkCanvas,
    nodes: Sequence[tuple[float, float]],
    stops,
    width: float = 1.5,
) -> None:
    """Blockchain-ship sail mesh: nodes + edges."""
    s = ink.size
    pts = [(x * s, y * s) for x, y in nodes]
    # connect each node to nearest 2–3 others
    for i, p in enumerate(pts):
        dists = sorted(
            ((math.hypot(p[0] - q[0], p[1] - q[1]), j) for j, q in enumerate(pts) if j != i),
        )
        for _, j in dists[:3]:
            if j > i:
                ink.stroke([p, pts[j]], stops, width, 140)
    for p in pts:
        r = max(2.0, s * 0.004)
        ink.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], stops, 200)


def chain_links(
    ink: InkCanvas,
    p0: tuple[float, float],
    p1: tuple[float, float],
    n: int,
    stops,
    scale: float = 0.012,
) -> None:
    s = ink.size
    for i in range(n):
        t = i / max(1, n - 1)
        x = lerp(p0[0], p1[0], t) * s
        y = lerp(p0[1], p1[1], t) * s
        r = scale * s
        ink.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], stops, 0,
                    outline_w=max(1, int(s * 0.002)))


def smoke_flourish(
    ink: InkCanvas,
    origin: tuple[float, float],
    stops,
    strands: int = 4,
    height: float = 0.28,
    phase: float = 0.0,
) -> None:
    s = ink.size
    ox, oy = origin[0] * s, origin[1] * s
    for k in range(strands):
        pts = []
        for i in range(40):
            t = i / 39
            x = ox + s * height * 0.35 * math.sin(t * math.pi * 1.5 + phase + k * 0.9) * (0.4 + t)
            y = oy - s * height * t
            pts.append((x, y))
        ink.stroke(catmull(pts, 5), stops, max(1.5, s * 0.0022) * (1 - k * 0.12), 160 - k * 20)


def character_profile(
    ink: InkCanvas,
    hx: float,
    hy: float,
    r: float,
    stops,
    facing: float = 1.0,
    hair: bool = True,
    dissolve: bool = True,
    fill_alpha: int = 55,
) -> None:
    """Gestural Amano-ish figure: profile head, tousled hair, dissolving lower body."""
    s = ink.size
    cx, cy, rr = hx * s, hy * s, r * s
    # head oval
    head = [
        (cx + facing * rr * 0.9, cy - rr * 0.2),
        (cx + facing * rr * 0.3, cy - rr * 1.05),
        (cx - facing * rr * 0.7, cy - rr * 0.5),
        (cx - facing * rr * 0.85, cy + rr * 0.3),
        (cx - facing * rr * 0.2, cy + rr * 0.95),
        (cx + facing * rr * 0.7, cy + rr * 0.55),
    ]
    head_s = catmull(head + [head[0]], 10)
    ink.fill_poly(head_s, stops, alpha=max(8, fill_alpha // 2), y_sample=cy)
    ink.stroke(head_s, stops, max(2.4, s * 0.0035), 240)
    # facial contour hatch
    for i in range(3):
        ink.stroke(
            qbez(
                (cx - facing * rr * 0.5, cy - rr * 0.3 + i * rr * 0.2),
                (cx, cy + i * rr * 0.15),
                (cx + facing * rr * 0.55, cy - rr * 0.1 + i * rr * 0.18),
                12,
            ),
            stops, max(1.0, s * 0.0015), 120,
        )
    # eye
    ex = cx + facing * rr * 0.25
    ey = cy - rr * 0.05
    ink.ellipse([ex - rr * 0.28, ey - rr * 0.22, ex + rr * 0.28, ey + rr * 0.22], stops, 40)
    ink.ellipse([ex - rr * 0.28, ey - rr * 0.22, ex + rr * 0.28, ey + rr * 0.22], stops, 0,
                outline_w=max(1, int(s * 0.002)))
    ink.ellipse([ex - rr * 0.08, ey - rr * 0.08, ex + rr * 0.1, ey + rr * 0.1],
                [(13, 13, 22)] * 3, 230)
    if hair:
        hair_stops = [(20, 12, 28), (40, 20, 50), (15, 18, 45), (10, 12, 30)]
        for k in range(7):
            pts = qbez(
                (cx - facing * rr * 0.55, cy - rr * (0.4 + k * 0.05)),
                (cx - facing * rr * (0.1 + k * 0.12), cy - rr * (1.5 + k * 0.18)),
                (cx + facing * rr * (0.7 + k * 0.12), cy - rr * (0.2 + k * 0.15)),
                22,
            )
            ink.stroke(pts, hair_stops, max(2.0, s * 0.0035) - k * 0.15, 240)
    # torso dissolving into tendrils
    shoulder = (cx - facing * rr * 0.3, cy + rr * 1.1)
    hip = (cx - facing * rr * 0.1, cy + rr * 4.2)
    torso_l = qbez(shoulder, (cx - facing * rr * 1.4, cy + rr * 2.5), hip, 16)
    torso_r = qbez(
        (cx + facing * rr * 0.9, cy + rr * 1.0),
        (cx + facing * rr * 1.2, cy + rr * 2.8),
        (cx + facing * rr * 0.2, cy + rr * 4.0),
        16,
    )
    body = torso_l + list(reversed(torso_r))
    ink.fill_poly(body, stops, alpha=max(10, fill_alpha // 2), y_sample=cy + rr * 2.5)
    ink.stroke(torso_l, stops, max(2.4, s * 0.0035), 230)
    ink.stroke(torso_r, stops, max(2.4, s * 0.0035), 230)
    # jacket fold hatches
    for i in range(5):
        ink.stroke(
            qbez(
                (cx - facing * rr * 0.6, cy + rr * (1.4 + i * 0.45)),
                (cx + facing * rr * 0.2, cy + rr * (1.8 + i * 0.4)),
                (cx + facing * rr * 0.9, cy + rr * (1.5 + i * 0.45)),
                14,
            ),
            stops, max(1.0, s * 0.0016), 140,
        )
    if dissolve:
        for i in range(7):
            bx = cx + (i - 3) * rr * 0.45
            ink.stroke(
                qbez(
                    (bx, cy + rr * 3.6),
                    (bx + facing * rr * 0.5, cy + rr * 5.0),
                    (bx - facing * rr * 0.4, cy + rr * 6.5),
                    20,
                ),
                stops, max(1.4, s * 0.0022), 170,
            )


def placeholder_tag(ink: InkCanvas, slot: int, color=(100, 100, 120)) -> None:
    """Discreet corner checker — marks procedural stand-ins."""
    s = ink.size
    cell = max(3, s // 128)
    x0 = (slot * 7 + 2) * cell
    y0 = s - 3 * cell
    for i in range(4):
        if i % 2 == 0:
            ink.draw.rectangle(
                [x0 + i * cell, y0, x0 + (i + 1) * cell - 1, y0 + cell - 1],
                fill=(*color, 120),
            )


def bone_canvas(size: int, tint: tuple[int, int, int] = (244, 244, 240)) -> Image.Image:
    return Image.new("RGBA", (size, size), (*tint, 255))


def grade_vertical_ink(
    img: Image.Image,
    stops: Sequence[Sequence[int]] | None = None,
    strength: float = 0.72,
    white_cut: int = 232,
) -> Image.Image:
    """Remap non-white ink toward a vertical colour ramp (ships_amano DNA).

    Preserves luminance and alpha; shifts chroma of stroke pixels so the
    whole composite reads warm-top → cool-bottom even when layered traits
    were drawn with mismatched local ramps.
    """
    import numpy as np

    if stops is None:
        stops = RAMPS["crimson_navy"]
    arr = np.asarray(img.convert("RGBA"), dtype=np.float32)
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3]
    a = arr[:, :, 3]
    luma = rgb.mean(axis=2)
    # ink = opaque-enough and not bone-white ground
    mask = (a > 40) & (luma < white_cut)
    if not mask.any():
        return img

    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    # build ramp image
    ramp = np.zeros((h, 3), dtype=np.float32)
    for y in range(h):
        ramp[y] = ramp_color(stops, float(y) / max(1, h - 1))
    target = ramp[:, None, :].repeat(w, axis=1)

    # luminance-preserving blend toward ramp colour
    out = rgb.copy()
    tl = target.mean(axis=2, keepdims=True)
    tl = np.maximum(tl, 1.0)
    # scale ramp to match local luma
    scaled = target * (luma[:, :, None] / tl)
    blended = rgb * (1.0 - strength) + scaled * strength
    out[mask] = blended[mask]
    out = np.clip(out, 0, 255)
    result = np.dstack([out, a]).astype(np.uint8)
    return Image.fromarray(result, "RGBA")


def soft_atmosphere(
    ink: InkCanvas,
    stops,
    density: int = 6,
    alpha: int = 28,
) -> None:
    """Barely-there sky wisps — never a solid fill band."""
    s = ink.size
    for i in range(density):
        y = s * (0.08 + i * 0.06)
        pts = catmull([
            (s * 0.05, y),
            (s * 0.3, y + s * 0.01 * ((i % 3) - 1)),
            (s * 0.6, y - s * 0.008 * ((i % 2) - 0.5)),
            (s * 0.95, y + s * 0.006),
        ], 6)
        ink.stroke(pts, stops, max(1.0, s * 0.0012), alpha)
