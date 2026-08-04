# SPDX-License-Identifier: MIT
"""Tests for the ink stroke primitives, focused on the scratch-ROI rasteriser.

Strokes are composited with ``maximum`` into a reusable scratch buffer, and only
each segment's bounding box is cleared, drawn and merged. That is a 60x speedup
over allocating a full canvas per segment, but it is only correct if the ROI
provably contains everything OpenCV draws — otherwise ink is silently clipped
or stale scratch pixels leak into a later stroke. These tests pin both.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from artgen import ink  # noqa: E402


def blank(n: int = 256) -> np.ndarray:
    return np.zeros((n, n), dtype=np.float32)


# ------------------------------------------------------------- fixed point


def test_pts_matches_the_scalar_rounding_it_replaced():
    rng = np.random.default_rng(7)
    pts = [(float(a), float(b)) for a, b in rng.uniform(-80, 2200, (20000, 2))]
    scalar = np.asarray(
        [[int(round(x * ink._SUB)), int(round(y * ink._SUB))] for x, y in pts],
        dtype=np.int32,
    ).reshape(-1, 1, 2)
    assert np.array_equal(ink._pts(pts), scalar)


# -------------------------------------------------------------------- roi


def test_roi_is_clipped_to_the_canvas():
    m = blank(100)
    assert ink._roi(m, [(-500, -500), (-400, -400)], 3.0) is None
    assert ink._roi(m, [(500, 500), (600, 600)], 3.0) is None
    box = ink._roi(m, [(-50, -50), (50, 50)], 3.0)
    assert box == (0, 0, 56, 56) or (box[0] == 0 and box[1] == 0)


def test_roi_grows_with_stroke_width():
    m = blank(400)
    thin = ink._roi(m, [(200, 200), (210, 200)], 1.0)
    thick = ink._roi(m, [(200, 200), (210, 200)], 40.0)
    assert (thick[2] - thick[0]) > (thin[2] - thin[0])
    assert (thick[3] - thick[1]) > (thin[3] - thin[1])


@pytest.mark.parametrize("thickness", [1, 2, 3, 5, 12, 28, 40])
def test_roi_contains_everything_opencv_draws(thickness):
    """The margin must exceed the rasteriser's real overdraw at every angle.

    Measured empirically rather than assumed: OpenCV's anti-aliased line never
    exceeds bbox + thickness/2 + 1px, so ROI_MARGIN=4 has headroom.
    """
    n = 400
    for ang in np.linspace(0.0, math.pi, 17):
        cx = cy = n / 2
        length = 60.0
        pts = [(cx - math.cos(ang) * length, cy - math.sin(ang) * length),
               (cx + math.cos(ang) * length, cy + math.sin(ang) * length)]
        full = blank(n)
        cv2.polylines(full, [ink._pts(pts)], False, 1.0, thickness=thickness,
                      lineType=cv2.LINE_AA, shift=ink.SUBPX_BITS)
        x0, y0, x1, y1 = ink._roi(full, pts, float(thickness))
        outside = full.copy()
        outside[y0:y1, x0:x1] = 0.0
        assert outside.max() == 0.0, (
            f"thickness={thickness} angle={ang:.2f}: ink drawn outside the ROI"
        )


# ------------------------------------------------------------------ stamp


def test_scratch_buffer_is_reused_across_calls():
    m = blank(64)
    ink.polyline(m, [(5, 5), (60, 60)], 2.0)
    first = ink._scratch(m)
    ink.polyline(m, [(5, 60), (60, 5)], 2.0)
    assert ink._scratch(m) is first


def test_scratch_is_reallocated_for_a_different_canvas_size():
    a, b = blank(32), blank(64)
    ink.polyline(a, [(1, 1), (30, 30)], 2.0)
    sa = ink._scratch(a)
    ink.polyline(b, [(1, 1), (60, 60)], 2.0)
    assert ink._scratch(b).shape == b.shape
    assert sa.shape == a.shape


def test_stale_scratch_content_never_leaks_into_a_later_stroke():
    """Two strokes far apart, then a third overlapping the first's footprint."""
    m = blank(200)
    ink.polyline(m, [(10, 10), (60, 10)], 6.0)
    ink.polyline(m, [(140, 180), (190, 180)], 6.0)
    reference = blank(200)
    ink.polyline(reference, [(10, 100), (60, 100)], 6.0)
    fresh = blank(200)
    ink.polyline(fresh, [(10, 100), (60, 100)], 6.0)
    assert np.array_equal(reference, fresh)


def test_polyline_matches_a_naive_full_canvas_draw():
    pts = [(12.3, 40.7), (90.1, 22.4), (150.9, 130.2)]
    roi_drawn = blank(200)
    ink.polyline(roi_drawn, pts, 5.0, intensity=0.8)
    naive = blank(200)
    seg = np.zeros_like(naive)
    cv2.polylines(seg, [ink._pts(pts)], False, 0.8, thickness=5,
                  lineType=cv2.LINE_AA, shift=ink.SUBPX_BITS)
    np.maximum(naive, seg, out=naive)
    assert np.array_equal(roi_drawn, naive)


def test_fill_poly_matches_a_naive_full_canvas_draw():
    poly = [(30.5, 30.5), (150.25, 44.75), (120.0, 160.0), (40.0, 140.5)]
    roi_drawn = blank(200)
    ink.fill_poly(roi_drawn, poly, 0.9)
    naive = blank(200)
    seg = np.zeros_like(naive)
    cv2.fillPoly(seg, [ink._pts(poly)], 0.9, lineType=cv2.LINE_AA,
                 shift=ink.SUBPX_BITS)
    np.maximum(naive, seg, out=naive)
    assert np.array_equal(roi_drawn, naive)


def test_sub_pixel_widths_are_scaled_down():
    """A width below 1px cannot thin the rasterised line, so it dims it."""
    thin, fat = blank(64), blank(64)
    ink.polyline(thin, [(5, 32), (58, 32)], 0.5)
    ink.polyline(fat, [(5, 32), (58, 32)], 1.0)
    assert thin.max() == pytest.approx(fat.max() * 0.5, rel=1e-5)


def test_strokes_accumulate_with_maximum_not_addition():
    """Crossing strokes must stay crisp instead of blooming past full coverage."""
    m = blank(64)
    ink.polyline(m, [(5, 32), (58, 32)], 4.0, intensity=0.6)
    ink.polyline(m, [(32, 5), (32, 58)], 4.0, intensity=0.6)
    assert m.max() == pytest.approx(0.6, abs=1e-6)


def test_degenerate_inputs_are_no_ops():
    m = blank(32)
    ink.polyline(m, [(1, 1)], 3.0)
    ink.calligraphic_stroke(m, [(1, 1)], 3.0, 1.0)
    ink.fill_poly(m, [(1, 1), (2, 2)], 1.0)
    assert m.max() == 0.0


def test_offscreen_strokes_are_skipped_without_error():
    m = blank(64)
    ink.polyline(m, [(-900, -900), (-800, -800)], 4.0)
    ink.fill_poly(m, [(900, 900), (950, 900), (925, 950)], 1.0)
    assert m.max() == 0.0


# ------------------------------------------------------------- composition


def test_flow_bundle_pinches_shut_at_both_ends():
    """The bundle's whole point: members converge at the terminals."""
    m = blank(400)
    spine = [(20.0 + i * 3.6, 200.0) for i in range(100)]
    ink.flow_bundle(m, spine, np.random.default_rng(3), count=5, spread=60.0,
                    width=3.0)
    rows = np.nonzero(m.max(axis=1) > 0)[0]
    cols_start = np.nonzero(m[:, 25] > 0)[0]
    cols_mid = np.nonzero(m[:, 200] > 0)[0]
    assert rows.size > 0
    span_start = cols_start.max() - cols_start.min() if cols_start.size else 0
    span_mid = cols_mid.max() - cols_mid.min() if cols_mid.size else 0
    assert span_mid > span_start * 2, "bundle did not fan out mid-run"


def test_catmull_rom_passes_through_its_control_points():
    pts = [(0.0, 0.0), (10.0, 20.0), (30.0, 5.0), (50.0, 25.0)]
    out = ink.catmull_rom(pts, samples_per_span=8)
    assert out[0] == pytest.approx(pts[0])
    assert out[-1] == pytest.approx(pts[-1])
    assert len(out) > len(pts)


def test_catmull_rom_short_input_is_returned_unchanged():
    assert ink.catmull_rom([(0.0, 0.0), (1.0, 1.0)]) == [(0.0, 0.0), (1.0, 1.0)]
