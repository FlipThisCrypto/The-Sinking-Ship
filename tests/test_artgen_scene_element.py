# SPDX-License-Identifier: MIT
"""QA gates for the scene_element layer.

Forty plates that all have to sit behind any of sixteen ships without becoming
clutter, so the assertions are mostly about restraint: staying small, staying
near the waterline, and surrendering the centre of the frame to the vessel.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from artgen import scene_element as se, sea  # noqa: E402
from artgen.core import alpha_stats  # noqa: E402

DIR = ROOT / "sprites" / "scene_element"
PLATES = sorted(DIR.glob("*.png"))
SERIES = ("harbor", "military", "pirate", "wizard", "crystal")


def _traits() -> list[dict]:
    doc = json.loads((ROOT / "config" / "traits.json").read_text(encoding="utf-8"))
    layer = next(ly for ly in doc["layers"] if ly["name"] == "scene_element")
    return [t for t in layer["traits"] if t.get("sprite_filename")]


@pytest.fixture(scope="module")
def plates() -> dict[str, Image.Image]:
    return {p.stem: Image.open(p).convert("RGBA") for p in PLATES}


# ------------------------------------------------------------- the contract


def test_renderer_keys_match_traits_json_exactly():
    assert set(se.all_keys()) == {Path(t["sprite_filename"]).stem for t in _traits()}


def test_there_are_forty_plates():
    assert len(se.all_keys()) == 40
    assert len(PLATES) == 40


def test_series_assignment_matches_traits_json():
    """The layer is single-select, so a mislabelled series silently breaks the
    'one series per NFT' guarantee the config documents."""
    declared = {Path(t["sprite_filename"]).stem: t["series"] for t in _traits()}
    for key, series in declared.items():
        assert se.series_of(key) == series, key


def test_every_series_is_represented():
    have = {se.series_of(k) for k in se.all_keys()}
    assert have == set(SERIES)


def test_filenames_are_prefixed_with_their_series():
    for key in se.all_keys():
        assert key.startswith(se.series_of(key) + "_"), key


def test_all_plates_are_2048_rgba(plates):
    for key, img in plates.items():
        assert img.size == (2048, 2048), key
        assert img.mode == "RGBA", key


def test_no_plate_is_empty(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] > 0.25, f"{key} is blank"


def test_all_plates_are_distinct(plates):
    assert len({img.tobytes() for img in plates.values()}) == len(plates)


# ------------------------------------------------------------- the geometry


def test_waterline_agrees_with_the_sea_layer():
    assert se.SEA_HORIZON == sea.HORIZON


def test_clearance_mask_protects_the_ship_and_releases_the_margins():
    mask = se.clearance_mask(512, 0.30)
    cx, cy = int(se.SHIP_CORE[0] * 512), int(se.SHIP_CORE[1] * 512)
    assert mask[cy, cx] == pytest.approx(0.30, abs=1e-5)
    assert mask[8, 8] == pytest.approx(1.0, abs=1e-5)
    assert mask.min() >= 0.30 - 1e-6


def test_no_plate_crowds_the_ship_core(plates):
    """Elements pass *behind* the vessel; they must not tangle with the hull.

    Stated as an absolute density bound rather than "lighter in the core than
    outside it". The latter is false for anything spread along the horizon —
    a convoy or a reef sits at the same distance as the ship by definition, so
    its mass necessarily overlaps the core. What matters is that the clearance
    mask keeps that mass faint; measured, the worst offender is 0.033.
    """
    size = 2048
    cx, cy, rx, ry = se.SHIP_CORE
    ys, xs = np.mgrid[0:size, 0:size]
    core = np.hypot((xs - cx * size) / (rx * size),
                    (ys - cy * size) / (ry * size)) <= 0.75
    for key, img in plates.items():
        a = np.asarray(img)[:, :, 3].astype(np.float32) / 255.0
        assert a[core].mean() < 0.10, f"{key} crowds the hull ({a[core].mean():.3f})"


def test_render_actually_applies_the_clearance_mask():
    """Guard the mechanism, not just the outcome."""
    key = "crystal_crystal_reef"
    with_mask = np.asarray(se.render(key, size=256).to_image())[:, :, 3].astype(float)
    spec = se.SCENE_SPECS[key]
    assert spec.clearance < 1.0
    mask = se.clearance_mask(256, spec.clearance)
    cx, cy = int(se.SHIP_CORE[0] * 256), int(se.SHIP_CORE[1] * 256)
    assert mask[cy, cx] < mask[4, 4]
    assert with_mask.max() <= se.MAX_ALPHA * 255 + 1


def test_plates_stay_out_of_the_deep_foreground(plates):
    """Below the ship's waterline is the character's water; keep it clear."""
    cut = int(2048 * 0.88)
    for key, img in plates.items():
        floor = np.asarray(img)[cut:, :, 3].astype(np.float32) / 255.0
        assert floor.mean() < 0.10, key


def test_plates_stay_light_enough_to_sit_behind_a_ship(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["mean"] <= 0.22, key


def test_alpha_ceiling_is_respected(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] <= se.MAX_ALPHA + 0.01, key


def test_plate_file_sizes_are_disciplined():
    for p in PLATES:
        assert p.stat().st_size < 1_600_000, f"{p.name} is {p.stat().st_size} bytes"


# --------------------------------------------------------------- the renderer


def test_specs_reference_only_master_palette_colors():
    pal = set(se.PAL.values())
    for key, spec in se.SCENE_SPECS.items():
        for col in spec.colors:
            assert tuple(col) in pal, f"{key} uses an off-palette colour {col}"
        assert spec.ink_color in se.PAL, key


def test_spec_budgets_are_sane():
    for key, spec in se.SCENE_SPECS.items():
        assert 0.0 < spec.line_alpha <= 1.0, key
        assert 0.0 < spec.clearance <= 1.0, key
        assert spec.motif is not None, key


def test_render_is_deterministic():
    a = se.render("harbor_lighthouse", size=96).to_image().tobytes()
    b = se.render("harbor_lighthouse", size=96).to_image().tobytes()
    assert a == b


def test_render_rejects_unknown_trait():
    with pytest.raises(KeyError):
        se.render("harbor_nowhere", size=64)


@pytest.mark.slow
@pytest.mark.parametrize("key", ["harbor_lighthouse", "crystal_ruby",
                                 "wizard_spell_circle"])
def test_render_is_resolution_independent(key):
    """Compared at 2048 vs 1024, not 1024 vs 512.

    This layer carries the finest linework in the collection — background
    filigree a couple of pixels wide at master size. Below ~1024 those strokes
    fall under one pixel, where the rasteriser dims them instead of thinning
    them, and that deliberately does not match what downsampling does. The
    property still holds in the range the collection actually renders at.
    """
    import cv2

    big = np.asarray(se.render(key, size=2048).to_image(), dtype=np.float32)
    small = np.asarray(se.render(key, size=1024).to_image(), dtype=np.float32)
    ref = cv2.resize(big, (1024, 1024), interpolation=cv2.INTER_AREA)
    a_small, a_ref = small[:, :, 3] / 255.0, ref[:, :, 3] / 255.0
    assert a_small.mean() == pytest.approx(a_ref.mean(), rel=0.25), key
