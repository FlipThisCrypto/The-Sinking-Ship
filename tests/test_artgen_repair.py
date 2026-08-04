# SPDX-License-Identifier: MIT
"""Tests for corrective transforms on externally authored art, and the gate
that keeps the repaired ``ship_class`` layer from regressing.

The repair is destructive to files that cannot be regenerated, so the safety
property is checked directly: the plate's appearance over bone white — the
composite ground the illustration profile uses — must not change.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from artgen.repair import (  # noqa: E402
    appearance_delta_over_white,
    matte_veil_strength,
    unmatte_over_white,
)

SHIPS = sorted((ROOT / "sprites" / "ship_class").glob("*.png"))


BORDER = 16


def _ink_on_white(size: int = 128, veil_alpha: int = 0,
                  transparent_corner: bool = False) -> Image.Image:
    """A dark stroke on white paper, optionally under a residual white veil.

    Mirrors the real defect: the veil covers the whole canvas including the
    border, and the ink sits well inside it so the border sample is pure veil.
    """
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[:, :, :3] = 246
    arr[:, :, 3] = veil_alpha
    mid = size // 2
    arr[mid - 8:mid + 8, BORDER * 2:size - BORDER * 2, :3] = 30   # the ink
    arr[mid - 8:mid + 8, BORDER * 2:size - BORDER * 2, 3] = 255
    if transparent_corner:
        arr[:BORDER, :BORDER] = 0
    return Image.fromarray(arr, mode="RGBA")


# ------------------------------------------------------- the transform itself


def test_unmatte_preserves_appearance_over_white():
    """The safety property: repairing must not change the plate over white.

    ``dmax`` is the guard. ``dmean`` is loose here only because this fixture is
    100% veil; real plates are ~70% authored-transparent, so their mean shift
    is an order of magnitude smaller (see the vault comparison below).
    """
    src = _ink_on_white(veil_alpha=150)
    dmax, dmean = appearance_delta_over_white(src, unmatte_over_white(src))
    assert dmax <= 2.0
    assert dmean < 0.5


def test_unmatte_removes_a_white_veil():
    src = _ink_on_white(veil_alpha=150)
    assert matte_veil_strength(src, BORDER) > 0.5
    # A near-white veil cannot reach exactly zero — 246/255 white is still
    # 3.5% ink by this model — but it drops from "bleaches the sky" to
    # "indistinguishable", which is the whole point.
    assert matte_veil_strength(unmatte_over_white(src), BORDER) < 0.04


def test_unmatte_keeps_the_ink_opaque():
    out = np.asarray(unmatte_over_white(_ink_on_white(veil_alpha=150)))
    assert out[64, 64, 3] > 200


def test_unmatte_respects_authored_transparency():
    """Dark leftover RGB under alpha==0 must not be resurrected as ink.

    Several plates carry it — aircraft_carrier goes down to 0 — and deriving
    alpha from colour alone would paint it back in.
    """
    arr = np.zeros((16, 16, 4), dtype=np.uint8)
    arr[:, :, :3] = 12          # dark RGB ...
    arr[:, :, 3] = 0            # ... but the author marked it transparent
    out = np.asarray(unmatte_over_white(Image.fromarray(arr, mode="RGBA")))
    assert out[:, :, 3].max() == 0


def test_unmatte_keeps_saturated_colour_solid():
    """min-across-channels, not luminance: a pure red stroke stays opaque."""
    arr = np.zeros((8, 8, 4), dtype=np.uint8)
    arr[:, :, :3] = 255
    arr[:, :, 3] = 0
    arr[4, 4] = (255, 0, 0, 255)
    out = np.asarray(unmatte_over_white(Image.fromarray(arr, mode="RGBA")))
    assert out[4, 4, 3] == 255
    assert tuple(out[4, 4, :3]) == (255, 0, 0)


def test_unmatte_is_idempotent():
    once = unmatte_over_white(_ink_on_white(veil_alpha=150))
    twice = unmatte_over_white(once)
    dmax, _ = appearance_delta_over_white(once, twice)
    assert dmax <= 1.0
    assert np.abs(np.asarray(once).astype(int)
                  - np.asarray(twice).astype(int)).max() <= 1


def test_unmatte_zeroes_rgb_under_transparent_pixels():
    src = _ink_on_white(veil_alpha=120, transparent_corner=True)
    out = np.asarray(unmatte_over_white(src))
    transparent = out[:, :, 3] == 0
    assert transparent.any()
    assert out[:, :, :3][transparent].max() == 0


def test_appearance_delta_is_zero_for_identical_plates():
    src = _ink_on_white(veil_alpha=40)
    assert appearance_delta_over_white(src, src) == (0.0, 0.0)


def test_veil_strength_is_zero_for_a_clean_border():
    assert matte_veil_strength(_ink_on_white(veil_alpha=0), BORDER) == pytest.approx(0.0)


# --------------------------------------------------- the shipped layer's state


def test_ship_class_has_sixteen_plates():
    assert len(SHIPS) == 16


@pytest.mark.parametrize("path", SHIPS, ids=lambda p: p.stem)
def test_no_ship_plate_carries_a_residual_matte(path):
    """A veil is invisible on bone white but bleaches any coloured sky behind it.

    lifeboat once reached alpha 148/255 in a corner, veiling the whole frame.
    """
    veil = matte_veil_strength(Image.open(path).convert("RGBA"))
    assert veil < 0.005, f"{path.stem} border alpha {veil:.4f}"


@pytest.mark.parametrize("path", SHIPS, ids=lambda p: p.stem)
def test_no_ship_plate_is_a_full_canvas_rectangle(path):
    """Real artwork leaves margins; a full-bleed bbox means leftover matte."""
    a = np.asarray(Image.open(path).convert("RGBA"))[:, :, 3]
    ys, xs = np.nonzero(a > 32)
    assert xs.size, path.stem
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    assert bbox != (0, 0, 2047, 2047), f"{path.stem} covers the whole canvas"


@pytest.mark.parametrize("path", SHIPS, ids=lambda p: p.stem)
def test_ship_plates_are_2048_rgba_with_clean_transparency(path):
    img = Image.open(path).convert("RGBA")
    assert img.size == (2048, 2048)
    arr = np.asarray(img)
    transparent = arr[:, :, 3] == 0
    if transparent.any():
        assert arr[:, :, :3][transparent].max() == 0, (
            f"{path.stem} has noisy RGB under transparent pixels"
        )


@pytest.mark.parametrize("path", SHIPS, ids=lambda p: p.stem)
def test_shipped_repair_did_not_change_the_plate_over_white(path):
    """Compare every repaired plate against its frozen pre-repair original.

    This is the real safety statement — the synthetic fixtures above only test
    the transform in isolation. `vault/sprites-v1/` holds the byte-exact art as
    it was before the round, so the whole destructive edit is auditable.
    """
    original = ROOT / "vault" / "sprites-v1" / "ship_class" / path.name
    assert original.is_file(), f"no vaulted original for {path.name}"
    dmax, dmean = appearance_delta_over_white(
        Image.open(original).convert("RGBA"), Image.open(path).convert("RGBA")
    )
    assert dmax <= 2.0, f"{path.stem} shifted by {dmax:.1f}/255 over white"
    assert dmean < 0.1, f"{path.stem} mean shift {dmean:.3f}"


def test_ship_layer_size_is_disciplined():
    total = sum(p.stat().st_size for p in SHIPS)
    assert total < 55 * 1024 * 1024, f"ship_class is {total / 1048576:.1f} MB"
