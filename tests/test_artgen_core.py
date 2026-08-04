# SPDX-License-Identifier: MIT
"""Tests for engine/artgen core primitives.

These guard the two properties every layer renderer depends on: compositing is
correct source-over in straight alpha, and output is deterministic (44,444
mints are rendered from these sprites, and the fairness pipeline hashes them).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from artgen import BONE_WHITE, HORIZON, MASTER_PX  # noqa: E402
from artgen.core import (  # noqa: E402
    Canvas,
    alpha_stats,
    domain_warp,
    fbm,
    hex_to_rgb,
    load_palette,
    ramp_color,
    ramp_image,
    rng_for,
    save_sprite,
    seed_for,
    smoothstep,
    unique_colors,
    value_noise,
)


def test_module_constants_match_configs():
    assert MASTER_PX == 2048
    assert 0.0 < HORIZON < 1.0
    assert load_palette()["bone_white"] == BONE_WHITE


def test_hex_to_rgb():
    assert hex_to_rgb("#0d0d16") == (13, 13, 22)
    assert hex_to_rgb("f4f4f0") == (244, 244, 240)


def test_palette_loads_all_32_master_colors():
    pal = load_palette()
    assert len(pal) == 32
    assert all(len(v) == 3 and all(0 <= c <= 255 for c in v) for v in pal.values())


# ------------------------------------------------------------- determinism


def test_seed_for_is_stable_and_key_sensitive():
    assert seed_for("sky/aurora") == seed_for("sky/aurora")
    assert seed_for("sky/aurora") != seed_for("sky/fog")
    assert 0 <= seed_for("x") < 2 ** 63


def test_rng_for_reproduces_the_same_draws():
    a = rng_for("sky/fog").random(16)
    b = rng_for("sky/fog").random(16)
    assert np.array_equal(a, b)


def test_noise_is_deterministic_and_in_unit_range():
    n1 = value_noise(64, 64, 5, rng_for("k"))
    n2 = value_noise(64, 64, 5, rng_for("k"))
    assert np.array_equal(n1, n2)
    assert 0.0 <= n1.min() and n1.max() <= 1.0


def test_fbm_is_normalised_and_deterministic():
    f1 = fbm(64, 64, rng_for("f"), octaves=4, cells=3)
    f2 = fbm(64, 64, rng_for("f"), octaves=4, cells=3)
    assert np.array_equal(f1, f2)
    assert f1.min() == pytest.approx(0.0, abs=1e-5)
    assert f1.max() == pytest.approx(1.0, abs=1e-5)


def test_domain_warp_preserves_shape_and_moves_pixels():
    field = fbm(64, 64, rng_for("w"), octaves=3, cells=3)
    warped = domain_warp(field, rng_for("w2"), amount=8.0)
    assert warped.shape == field.shape
    assert not np.array_equal(warped, field)


# ------------------------------------------------------------------ ramps


def test_ramp_color_endpoints_and_midpoint():
    stops = [(0, 0, 0), (100, 200, 40)]
    assert ramp_color(stops, 0.0) == (0, 0, 0)
    assert ramp_color(stops, 1.0) == (100, 200, 40)
    assert ramp_color(stops, 0.5) == (50, 100, 20)


def test_ramp_color_clamps_out_of_range_t():
    stops = [(10, 10, 10), (20, 20, 20)]
    assert ramp_color(stops, -5.0) == (10, 10, 10)
    assert ramp_color(stops, 9.0) == (20, 20, 20)


def test_ramp_color_single_stop():
    assert ramp_color([(7, 8, 9)], 0.3) == (7, 8, 9)


def test_ramp_image_spans_only_the_requested_band():
    stops = [(0, 0, 0), (255, 255, 255)]
    img = ramp_image(stops, 100, 4, t0=0.0, t1=0.5)
    assert img.shape == (100, 4, 3)
    assert img[0, 0, 0] == pytest.approx(0.0, abs=1.0)
    # rows past t1 clamp to the final stop rather than continuing to ramp
    assert img[60, 0, 0] == pytest.approx(255.0, abs=1.0)
    assert img[99, 0, 0] == pytest.approx(255.0, abs=1.0)


def test_smoothstep_monotonic_and_bounded():
    x = np.linspace(-1, 2, 50)
    y = smoothstep(0.0, 1.0, x)
    assert y.min() >= 0.0 and y.max() <= 1.0
    assert np.all(np.diff(y) >= -1e-6)


def test_smoothstep_supports_inverted_edges():
    """edge0 > edge1 must fall from 1 to 0 — the sky alpha envelope relies on it."""
    y = smoothstep(1.0, 0.0, np.array([0.0, 0.5, 1.0], dtype=np.float32))
    assert y[0] == pytest.approx(1.0)
    assert y[-1] == pytest.approx(0.0)
    assert y[1] == pytest.approx(0.5, abs=1e-6)


def test_smoothstep_degenerate_edges_is_a_hard_step():
    y = smoothstep(0.5, 0.5, np.array([0.4, 0.6]))
    assert list(y) == [0.0, 1.0]


# ----------------------------------------------------------------- canvas


def test_canvas_starts_fully_transparent():
    c = Canvas(8)
    assert c.alpha.max() == 0.0
    assert np.asarray(c.to_image())[:, :, 3].max() == 0


def test_over_opaque_layer_replaces_color():
    c = Canvas(4)
    c.over_color((10, 20, 30), np.ones((4, 4), dtype=np.float32))
    c.over_color((200, 100, 50), np.ones((4, 4), dtype=np.float32))
    assert c.alpha.min() == pytest.approx(1.0)
    assert tuple(c.rgb[0, 0]) == pytest.approx((200.0, 100.0, 50.0))


def test_over_accumulates_alpha_source_over():
    c = Canvas(4)
    half = np.full((4, 4), 0.5, dtype=np.float32)
    c.over_color((255, 0, 0), half)
    assert c.alpha[0, 0] == pytest.approx(0.5)
    c.over_color((0, 0, 255), half)
    # 0.5 + 0.5 * (1 - 0.5)
    assert c.alpha[0, 0] == pytest.approx(0.75)


def test_over_unmixes_color_so_low_alpha_keeps_hue():
    """A single 10% red pass must stay red, not drift toward black."""
    c = Canvas(4)
    c.over_color((255, 0, 0), np.full((4, 4), 0.1, dtype=np.float32))
    assert tuple(c.rgb[0, 0]) == pytest.approx((255.0, 0.0, 0.0))


def test_over_clamps_out_of_range_alpha():
    c = Canvas(4)
    c.over_color((1, 2, 3), np.full((4, 4), 5.0, dtype=np.float32))
    assert c.alpha.max() == pytest.approx(1.0)


def test_multiply_alpha_scales_and_clamps():
    c = Canvas(4)
    c.over_color((1, 2, 3), np.full((4, 4), 0.8, dtype=np.float32))
    c.multiply_alpha(0.5)
    assert c.alpha[0, 0] == pytest.approx(0.4)
    c.multiply_alpha(100.0)
    assert c.alpha[0, 0] == pytest.approx(1.0)


def test_copy_is_independent():
    c = Canvas(4)
    c.over_color((9, 9, 9), np.ones((4, 4), dtype=np.float32))
    d = c.copy()
    d.multiply_alpha(0.0)
    assert c.alpha.max() == pytest.approx(1.0)


def test_to_image_zeroes_rgb_under_transparent_pixels():
    c = Canvas(4)
    a = np.zeros((4, 4), dtype=np.float32)
    a[0, 0] = 1.0
    c.over_color((200, 30, 30), a)
    arr = np.asarray(c.to_image())
    assert tuple(arr[1, 1]) == (0, 0, 0, 0)
    assert arr[0, 0, 3] == 255


# --------------------------------------------------------------------- io


def test_save_sprite_writes_rgba_at_requested_size(tmp_path):
    c = Canvas(32)
    c.over_color((100, 120, 140), np.full((32, 32), 0.6, dtype=np.float32))
    out = tmp_path / "s.png"
    nbytes = save_sprite(c, out, size=64)
    assert nbytes > 0
    img = Image.open(out)
    assert img.size == (64, 64) and img.mode == "RGBA"


def test_save_sprite_alpha_hygiene_shrinks_noisy_transparent_rgb(tmp_path):
    """Noise under alpha=0 defeats PNG filters; the writer must strip it."""
    rng = np.random.default_rng(0)
    arr = np.zeros((256, 256, 4), dtype=np.uint8)
    arr[:, :, :3] = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
    noisy = Image.fromarray(arr, mode="RGBA")
    dirty = tmp_path / "dirty.png"
    noisy.save(dirty, format="PNG", optimize=True)
    clean = tmp_path / "clean.png"
    cleaned = save_sprite(noisy, clean, size=256)
    assert cleaned < dirty.stat().st_size / 4
    assert np.asarray(Image.open(clean))[:, :, :3].max() == 0


def test_save_sprite_is_byte_stable(tmp_path):
    c = Canvas(48)
    c.over_color((30, 60, 90), np.full((48, 48), 0.4, dtype=np.float32))
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    save_sprite(c, a, size=48)
    save_sprite(c.copy(), b, size=48)
    assert a.read_bytes() == b.read_bytes()


def test_alpha_stats_reports_coverage():
    c = Canvas(10)
    a = np.zeros((10, 10), dtype=np.float32)
    a[:5] = 1.0
    c.over_color((1, 2, 3), a)
    stats = alpha_stats(c.to_image())
    assert stats["max"] == pytest.approx(1.0)
    assert stats["coverage"] == pytest.approx(0.5, abs=0.01)
    assert stats["mean"] == pytest.approx(0.5, abs=0.01)


def test_unique_colors_ignores_transparent_pixels():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[0, 0] = (10, 20, 30, 255)
    arr[0, 1] = (40, 50, 60, 255)
    arr[1, 1] = (99, 99, 99, 0)
    assert unique_colors(Image.fromarray(arr, mode="RGBA")) == 2
