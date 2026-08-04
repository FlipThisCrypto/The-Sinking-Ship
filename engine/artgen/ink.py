# SPDX-License-Identifier: MIT
"""Stroke vocabulary for the Amano ink idiom.

Everything here rasterises into a float32 coverage mask (0..1) at canvas
resolution; the caller tints the mask through a colour ramp and composites it.
Separating coverage from colour is what makes "the gradient lives on the
stroke" cheap: one mask, one ramp, no per-segment colour bookkeeping.

Strokes are drawn with OpenCV's anti-aliased line rasteriser using fixed-point
sub-pixel coordinates (``shift=SUBPX_BITS``), which is what keeps 1-2 px
filigree from crawling at 2048x2048.
"""
from __future__ import annotations

import math
from typing import Sequence

import cv2
import numpy as np

from .core import blur, value_noise

Point = tuple[float, float]

SUBPX_BITS = 5
"""Fixed-point fraction bits for cv2 sub-pixel drawing (1/32 px)."""
_SUB = 1 << SUBPX_BITS


def _pts(points: Sequence[Point]) -> np.ndarray:
    return np.asarray(
        [[int(round(x * _SUB)), int(round(y * _SUB))] for x, y in points],
        dtype=np.int32,
    ).reshape(-1, 1, 2)


# ------------------------------------------------------------------ curves


def catmull_rom(points: Sequence[Point], samples_per_span: int = 24) -> list[Point]:
    """Smooth open spline through ``points`` (duplicated end tangents)."""
    pts = list(points)
    if len(pts) < 3:
        return pts
    ext = [pts[0]] + pts + [pts[-1]]
    out: list[Point] = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for j in range(samples_per_span):
            t = j / samples_per_span
            t2, t3 = t * t, t * t * t
            out.append((
                0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
            ))
    out.append(pts[-1])
    return out


def spiral(cx: float, cy: float, r0: float, r1: float, turns: float,
           phase: float = 0.0, samples: int = 160,
           squash: float = 1.0) -> list[Point]:
    """Logarithmic-ish curl — the filigree unit of the reference art."""
    out: list[Point] = []
    for i in range(samples + 1):
        t = i / samples
        ang = phase + turns * 2.0 * math.pi * t
        r = r0 + (r1 - r0) * (t ** 1.35)
        out.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r * squash))
    return out


# ----------------------------------------------------------------- strokes


def calligraphic_stroke(mask: np.ndarray, points: Sequence[Point],
                        width_start: float, width_end: float,
                        *, taper: float = 1.0, intensity: float = 1.0) -> np.ndarray:
    """Draw a brush stroke whose width eases from ``width_start`` to ``width_end``.

    Rendered as a run of short anti-aliased segments at varying thickness and
    accumulated with ``maximum`` so overlapping ribs do not bloom into a blob —
    the ink stays crisp where strokes cross, as in the golden references.
    """
    pts = list(points)
    if len(pts) < 2:
        return mask
    n = len(pts) - 1
    for i in range(n):
        t = i / max(1, n - 1)
        # taper > 1 pushes the mass toward the head of the stroke
        e = t ** taper
        w = max(0.55, width_start + (width_end - width_start) * e)
        seg = np.zeros_like(mask)
        cv2.polylines(seg, [_pts(pts[i:i + 2])], False, float(intensity),
                      thickness=max(1, int(round(w))), lineType=cv2.LINE_AA,
                      shift=SUBPX_BITS)
        if w < 1.0:
            seg *= w
        np.maximum(mask, seg, out=mask)
    return mask


def polyline(mask: np.ndarray, points: Sequence[Point], width: float,
             intensity: float = 1.0, closed: bool = False) -> np.ndarray:
    """Constant-width anti-aliased polyline."""
    if len(points) < 2:
        return mask
    seg = np.zeros_like(mask)
    cv2.polylines(seg, [_pts(points)], closed, float(intensity),
                  thickness=max(1, int(round(width))), lineType=cv2.LINE_AA,
                  shift=SUBPX_BITS)
    if width < 1.0:
        seg *= width
    np.maximum(mask, seg, out=mask)
    return mask


def fill_poly(mask: np.ndarray, points: Sequence[Point],
              intensity: float = 1.0) -> np.ndarray:
    """Solid fill — used sparingly (crystals, hull shadow) per the style guide."""
    if len(points) < 3:
        return mask
    seg = np.zeros_like(mask)
    cv2.fillPoly(seg, [_pts(points)], float(intensity), lineType=cv2.LINE_AA,
                 shift=SUBPX_BITS)
    np.maximum(mask, seg, out=mask)
    return mask


def curl_flourish(mask: np.ndarray, cx: float, cy: float, radius: float,
                  rng: np.random.Generator, *, turns: float = 1.6,
                  width: float = 3.0, tail: float = 2.2) -> np.ndarray:
    """A curl with a drawn-out tail — the smoke/wave terminator motif."""
    phase = float(rng.uniform(0, 2 * math.pi))
    squash = float(rng.uniform(0.7, 1.15))
    core = spiral(cx, cy, radius * 0.08, radius, turns, phase, squash=squash)
    tail_len = radius * tail
    ang = phase + turns * 2 * math.pi
    tip = core[-1]
    tail_pts = catmull_rom([
        tip,
        (tip[0] + math.cos(ang + 0.5) * tail_len * 0.45,
         tip[1] + math.sin(ang + 0.5) * tail_len * 0.45),
        (tip[0] + math.cos(ang + 1.15) * tail_len * 0.85,
         tip[1] + math.sin(ang + 1.15) * tail_len * 0.85 - tail_len * 0.25),
    ])
    calligraphic_stroke(mask, core[::-1], width * 0.35, width)
    calligraphic_stroke(mask, tail_pts, width, width * 0.2, taper=1.4)
    return mask


def wave_ribbon(mask: np.ndarray, y: float, w: int, rng: np.random.Generator, *,
                amplitude: float = 40.0, wavelength: float = 520.0,
                width: float = 3.0, crest_curls: int = 3,
                curl_radius: float = 46.0) -> np.ndarray:
    """A horizontal wave line with curling crests — the sea's basic unit."""
    phase = float(rng.uniform(0, 2 * math.pi))
    jitter = float(rng.uniform(0.75, 1.3))
    xs = np.linspace(-w * 0.05, w * 1.05, 220)
    pts = [
        (float(x),
         y + math.sin(x / wavelength * 2 * math.pi * jitter + phase) * amplitude
         + math.sin(x / (wavelength * 0.37) * 2 * math.pi + phase * 1.7) * amplitude * 0.28)
        for x in xs
    ]
    calligraphic_stroke(mask, pts, width, width * 0.55, taper=0.9)
    for _ in range(crest_curls):
        i = int(rng.integers(20, len(pts) - 20))
        cx, cy = pts[i]
        curl_flourish(mask, cx, cy - curl_radius * 0.6, curl_radius, rng,
                      turns=float(rng.uniform(1.1, 1.9)), width=width * 0.9)
    return mask


def star_field(mask: np.ndarray, rng: np.random.Generator, count: int,
               *, y_range: tuple[float, float] = (0.0, 1.0),
               size_range: tuple[float, float] = (1.0, 3.2),
               sparkle_frac: float = 0.12) -> np.ndarray:
    """Points of light; a fraction get four-point sparkle rays."""
    h, w = mask.shape[:2]
    for _ in range(count):
        x = float(rng.uniform(0, w))
        y = float(rng.uniform(y_range[0] * h, y_range[1] * h))
        r = float(rng.uniform(*size_range))
        cv2.circle(mask, (int(round(x * _SUB)), int(round(y * _SUB))),
                   max(1, int(round(r * _SUB))), 1.0, -1, cv2.LINE_AA,
                   shift=SUBPX_BITS)
        if rng.random() < sparkle_frac:
            ray = r * float(rng.uniform(3.5, 7.0))
            polyline(mask, [(x - ray, y), (x + ray, y)], 1.0, 0.85)
            polyline(mask, [(x, y - ray), (x, y + ray)], 1.0, 0.85)
    return mask


def contour_strokes(mask: np.ndarray, field: np.ndarray, level: float, *,
                    width: float = 3.0, min_points: int = 40,
                    max_contours: int = 40, smooth: float = 6.0,
                    intensity: float = 1.0, min_area_frac: float = 0.004,
                    prefer_wide: float = 0.0, arc_frac: float = 1.0,
                    rng: np.random.Generator | None = None) -> np.ndarray:
    """Ink the iso-contours of a scalar ``field`` as calligraphic outlines.

    This is how cloud, wave and smoke forms get their edges: the same warped
    noise that drives the wash also supplies the linework, so the two always
    agree. Contours are Douglas-Peucker simplified then re-smoothed through a
    Catmull-Rom spline, which converts jagged marching-squares output into the
    long confident curves the reference art uses.

    Two filters keep the result from reading as scribble — the failure mode of
    naively inking every iso-line:

    ``min_area_frac``
        drop contours enclosing less than this fraction of the canvas, so only
        real cloud masses get an edge.
    ``prefer_wide``
        require ``bbox_width >= prefer_wide * bbox_height``; weather reads
        horizontally, and tall closed loops are what look like doodles.

    ``arc_frac`` < 1 inks only a contiguous run of each contour, leaving the
    form open — an unclosed edge is the single strongest cue that a line was
    brushed rather than traced.
    """
    h, w = mask.shape[:2]
    min_area = min_area_frac * h * w
    binary = (field >= level).astype(np.uint8)
    found, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    found = sorted(found, key=cv2.contourArea, reverse=True)
    drawn = 0
    for contour in found:
        if drawn >= max_contours:
            break
        if len(contour) < min_points or cv2.contourArea(contour) < min_area:
            continue
        _, _, bw, bh = cv2.boundingRect(contour)
        if prefer_wide > 0 and bw < prefer_wide * max(1, bh):
            continue
        approx = cv2.approxPolyDP(contour, max(1.5, smooth), True).reshape(-1, 2)
        if len(approx) < 5:
            continue
        pts = [(float(x), float(y)) for x, y in approx]
        if arc_frac < 1.0 and len(pts) > 6:
            keep = max(4, int(len(pts) * arc_frac))
            start = 0 if rng is None else int(rng.integers(0, len(pts)))
            pts = [pts[(start + i) % len(pts)] for i in range(keep)]
        pts = catmull_rom(pts, samples_per_span=10)
        w1 = width * (0.35 if rng is None else float(rng.uniform(0.25, 0.55)))
        calligraphic_stroke(mask, pts, width, w1, taper=1.25, intensity=intensity)
        drawn += 1
    return mask


def _normals(pts: Sequence[Point]) -> list[Point]:
    out: list[Point] = []
    n = len(pts)
    for i in range(n):
        ax, ay = pts[max(0, i - 1)]
        bx, by = pts[min(n - 1, i + 1)]
        dx, dy = bx - ax, by - ay
        m = math.hypot(dx, dy) or 1.0
        out.append((-dy / m, dx / m))
    return out


def flow_bundle(mask: np.ndarray, spine: Sequence[Point], rng: np.random.Generator,
                *, count: int = 4, spread: float = 26.0, width: float = 3.4,
                pinch: float = 1.0) -> np.ndarray:
    """Nested parallel curves that fan apart mid-run and converge at both ends.

    This — not the single line — is the reference art's flowing form: smoke,
    wave and hair are all drawn as a *bundle* whose members share a spine and
    pinch closed at the terminals. A lone stroke reads as wire; three or four
    that breathe together read as ink.
    """
    pts = list(spine)
    if len(pts) < 3:
        return mask
    norms = _normals(pts)
    n = len(pts)
    for k in range(count):
        # -1..1 across the bundle, skipping exact 0 when count is even
        u = (k / max(1, count - 1)) * 2.0 - 1.0
        jitter = float(rng.uniform(0.75, 1.25))
        offs: list[Point] = []
        for i, ((x, y), (nx, ny)) in enumerate(zip(pts, norms)):
            t = i / max(1, n - 1)
            # sin envelope: zero at both ends -> the bundle pinches shut
            env = math.sin(math.pi * t) ** pinch
            d = u * spread * env * jitter
            offs.append((x + nx * d, y + ny * d))
        w = width * float(rng.uniform(0.55, 1.15))
        calligraphic_stroke(mask, offs, w, w * 0.3, taper=1.35,
                            intensity=float(rng.uniform(0.65, 1.0)))
    return mask


def tendril(mask: np.ndarray, x0: float, y0: float, length: float, angle: float,
            rng: np.random.Generator, *, width: float = 4.0,
            curl_radius: float = 0.22, sway: float = 0.45,
            bundle: int = 4) -> np.ndarray:
    """A travelling flow-bundle terminating in a curl — the cloud/smoke wisp.

    Isolated spirals read as stickers; a spiral arrived at along a travelling
    bundle reads as ink. The workhorse for storm cloud, fire and aura.
    """
    n = 6
    pts = [(x0, y0)]
    ang = angle
    for i in range(1, n + 1):
        # curvature ramps along the run so the form arcs instead of wandering
        ang += float(rng.uniform(-sway, sway)) * (0.35 + i / n)
        step = length / n
        pts.append((pts[-1][0] + math.cos(ang) * step,
                    pts[-1][1] + math.sin(ang) * step))
    body = catmull_rom(pts, samples_per_span=16)
    flow_bundle(mask, body, rng, count=max(1, bundle),
                spread=length * 0.055, width=width, pinch=1.3)
    r = length * curl_radius
    tipx, tipy = body[-1]
    cx = tipx + math.cos(ang + math.pi / 2) * r
    cy = tipy + math.sin(ang + math.pi / 2) * r
    for j in range(min(3, max(1, bundle - 1))):
        curl = spiral(cx, cy, r * (1.0 - j * 0.22), r * 0.06,
                      float(rng.uniform(0.85, 1.45)),
                      phase=ang - math.pi / 2 + j * 0.22, samples=90,
                      squash=float(rng.uniform(0.75, 1.1)))
        calligraphic_stroke(mask, curl, width * 0.5, width * 0.12, taper=1.5)
    return mask


def sparks(mask: np.ndarray, rng: np.random.Generator, count: int, *,
           x_range: tuple[float, float] = (0.0, 1.0),
           y_range: tuple[float, float] = (0.0, 1.0),
           size: tuple[float, float] = (2.0, 9.0),
           rise: float = 2.6) -> np.ndarray:
    """Short rising embers — dense low, sparse high, never tall stalks."""
    h, w = mask.shape[:2]
    y0, y1 = y_range
    for _ in range(count):
        # bias upward-sparse: square the uniform draw toward the low end
        t = float(rng.random()) ** 0.45
        y = (y1 - (y1 - y0) * t) * h
        x = float(rng.uniform(*x_range)) * w
        r = float(rng.uniform(*size)) * (0.45 + 0.55 * t)
        drift = float(rng.uniform(-0.5, 0.5)) * r
        polyline(mask, [(x, y), (x + drift, y - r * rise)],
                 max(0.7, r * 0.30), float(rng.uniform(0.45, 1.0)))
    return mask


def glow(mask: np.ndarray, sigma: float, strength: float = 0.55) -> np.ndarray:
    """Soft halo around a coverage mask, clipped back into 0..1."""
    return np.clip(mask + blur(mask, sigma) * strength, 0.0, 1.0)


def ink_texture(mask: np.ndarray, rng: np.random.Generator, *,
                cells: int = 64, depth: float = 0.28) -> np.ndarray:
    """Break up flat coverage with brush grain so washes are not plastic."""
    h, w = mask.shape[:2]
    grain = value_noise(h, w, cells, rng)
    return np.clip(mask * (1.0 - depth + depth * grain * 2.0), 0.0, 1.0)
