# SPDX-License-Identifier: MIT
"""Tests for Amano ink drawing primitives (shipgen/amano_ink.py)."""
from __future__ import annotations

from shipgen.amano_ink import (
    RAMPS,
    InkCanvas,
    catmull,
    lerp,
    lerp_rgb,
    qbez,
    ramp_color,
)


def test_lerp_and_color_ramps():
    assert lerp(10.0, 20.0, 0.5) == 15.0
    c = lerp_rgb((0, 0, 0), (200, 100, 50), 0.5)
    assert c == (100, 50, 25)

    stops = RAMPS["crimson_navy"]
    top_col = ramp_color(stops, 0.0)
    bot_col = ramp_color(stops, 1.0)
    mid_col = ramp_color(stops, 0.5)

    assert top_col == stops[0]
    assert bot_col == stops[-1]
    assert isinstance(mid_col, tuple)
    assert len(mid_col) == 3


def test_spline_and_bezier_curves():
    pts = [(0.0, 0.0), (10.0, 5.0), (20.0, 0.0)]
    cb = catmull(pts, n_per=4)
    assert len(cb) > len(pts)

    qb = qbez((0.0, 0.0), (10.0, 20.0), (20.0, 0.0), n=5)
    assert len(qb) == 6
    assert qb[0] == (0.0, 0.0)
    assert qb[-1] == (20.0, 0.0)



def test_ink_canvas_rendering():
    ink = InkCanvas(256, y0=0.1, y1=0.9)
    assert ink.img.size == (256, 256)
    assert ink.img.mode == "RGBA"

    stops = RAMPS["steel_navy"]
    ink.stroke([(10, 10), (100, 100)], stops, width=2.0, alpha=200)
    ink.ellipse([20, 20, 80, 80], stops, alpha=150)

    extrema = ink.img.getextrema()
    # Check alpha channel is non-zero
    assert extrema[3][1] > 0
