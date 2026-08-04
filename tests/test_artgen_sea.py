# SPDX-License-Identifier: MIT
"""QA gates for the shipped sea layer and its renderer.

The sea's job is to meet the sky at the waterline without a seam and to leave
the frame legible for the eight layers stacked above it, so most of these
assertions are about *where* alpha is allowed to be, not about how it looks.
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

from artgen import sea, sky  # noqa: E402
from artgen.core import alpha_stats  # noqa: E402

SEA_DIR = ROOT / "sprites" / "sea"
PLATES = sorted(SEA_DIR.glob("*.png"))


def _traits_filenames() -> list[str]:
    doc = json.loads((ROOT / "config" / "traits.json").read_text(encoding="utf-8"))
    layer = next(ly for ly in doc["layers"] if ly["name"] == "sea")
    return [t["sprite_filename"] for t in layer["traits"] if t.get("sprite_filename")]


@pytest.fixture(scope="module")
def plates() -> dict[str, Image.Image]:
    return {p.stem: Image.open(p).convert("RGBA") for p in PLATES}


# ------------------------------------------------------------- the contract


def test_renderer_keys_match_traits_json_exactly():
    assert set(sea.all_keys()) == {Path(f).stem for f in _traits_filenames()}


def test_all_plates_are_2048_rgba(plates):
    for key, img in plates.items():
        assert img.size == (2048, 2048), key
        assert img.mode == "RGBA", key


def test_no_plate_is_empty(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] > 0.2, f"{key} is blank"


def test_all_plates_are_distinct(plates):
    assert len({img.tobytes() for img in plates.values()}) == len(plates)


def test_sea_and_sky_share_one_waterline():
    """A mismatch here puts a transparent gap or an overlap at the horizon."""
    assert sea.HORIZON == sky.HORIZON


def test_no_plate_bleeds_above_the_waterline(plates):
    """The sky owns everything above HORIZON; overlap muddies both."""
    cut = int(2048 * (sea.HORIZON - 0.045))
    for key, img in plates.items():
        above = np.asarray(img)[:cut, :, 3]
        assert above.max() <= 2, f"{key} bleeds into the sky"


def test_the_waterline_is_actually_covered(plates):
    """Sky alpha dies just past HORIZON, so sea must be present just below it."""
    lo = int(2048 * (sea.HORIZON + 0.02))
    hi = int(2048 * (sea.HORIZON + 0.09))
    for key, img in plates.items():
        band = np.asarray(img)[lo:hi, :, 3].astype(np.float32) / 255.0
        assert band.mean() > 0.06, f"{key} leaves a gap at the horizon"


def test_plates_leave_the_floor_clear(plates):
    """The character's water tendrils occupy the bottom of the frame."""
    cut = int(2048 * 0.97)
    for key, img in plates.items():
        floor = np.asarray(img)[cut:, :, 3].astype(np.float32) / 255.0
        assert floor.mean() < 0.30, f"{key} fills the floor"


def test_the_lower_hem_is_ragged_not_ruled(plates):
    """A dead-straight lower edge is the most artificial thing a sea can do.

    Measured as the spread of the per-column y where alpha last exceeds 10%.
    """
    for key, img in plates.items():
        a = np.asarray(img)[:, :, 3]
        cols = np.arange(0, 2048, 16)
        edges = []
        for x in cols:
            hits = np.nonzero(a[:, x] > 25)[0]
            if hits.size:
                edges.append(hits[-1])
        assert len(edges) > 100, key
        assert float(np.std(edges)) > 8.0, f"{key} has a ruled lower edge"


def test_alpha_ceiling_is_respected(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] <= sea.MAX_ALPHA + 0.01, key


def test_plates_stay_light_enough_to_layer_under(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["mean"] <= 0.32, key


def test_plate_file_sizes_are_disciplined():
    for p in PLATES:
        assert p.stat().st_size < 1_600_000, f"{p.name} is {p.stat().st_size} bytes"


# ------------------------------------------------------------- the renderer


def test_specs_reference_only_master_palette_colors():
    pal = set(sea.PAL.values())
    for key, spec in sea.SEA_SPECS.items():
        for stop in spec.stops:
            assert tuple(stop) in pal, f"{key} uses an off-palette stop {stop}"
        assert spec.ink_color in sea.PAL, key


def test_spec_budgets_are_sane():
    for key, spec in sea.SEA_SPECS.items():
        assert 0.0 < spec.wash_peak <= sea.MAX_ALPHA, key
        assert -1.0 <= spec.depth_bias <= 1.0, key
        assert spec.rows >= 1, key


def test_render_is_deterministic():
    a = sea.render("calm", size=96).to_image().tobytes()
    b = sea.render("calm", size=96).to_image().tobytes()
    assert a == b


def test_render_rejects_unknown_trait():
    with pytest.raises(KeyError):
        sea.render("no_such_sea", size=64)


def test_row_placement_stays_above_the_envelope_fade():
    """The frontmost row must be drawn where alpha still exists.

    Rows once ran to y=0.97 while the envelope died at 0.88, so the largest,
    nearest swells were painted into zero alpha and the sea read as a thin
    floating strip.
    """
    ctx = sea.SeaCtx(spec=sea.SEA_SPECS["calm"], size=1000,
                     rng=np.random.default_rng(0), canvas=None,
                     band=np.zeros((1, 1), dtype=np.float32))
    front = ctx.row_y(1.0) / 1000.0
    assert front == pytest.approx(sea.ROW_FRONT)
    for bias in (-1.0, 0.0, 1.0):
        env = sea._band_envelope(400, 1.0, bias, np.random.default_rng(1))
        row = int(400 * sea.ROW_FRONT)
        assert env[row].mean() > 0.25, f"depth_bias={bias} starves the front row"


@pytest.mark.parametrize("key", ["storm_swell", "frozen", "whirlpool"])
def test_render_is_resolution_independent(key):
    import cv2

    big = np.asarray(sea.render(key, size=1024).to_image(), dtype=np.float32)
    small = np.asarray(sea.render(key, size=512).to_image(), dtype=np.float32)
    ref = cv2.resize(big, (512, 512), interpolation=cv2.INTER_AREA)
    a_small = small[:, :, 3] / 255.0
    a_ref = ref[:, :, 3] / 255.0
    assert a_small.mean() == pytest.approx(a_ref.mean(), rel=0.22), key
    corr = np.corrcoef(a_small.mean(axis=1), a_ref.mean(axis=1))[0, 1]
    assert corr > 0.97, key
