# SPDX-License-Identifier: MIT
"""QA gates for the shipped sky layer and its renderer.

The image assertions run against the committed 2048px plates, so a regenerated
or hand-edited plate that violates the composition contract fails CI rather
than reaching a mint.
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

from artgen import sky  # noqa: E402
from artgen.core import alpha_stats  # noqa: E402

SKY_DIR = ROOT / "sprites" / "sky"
PLATES = sorted(SKY_DIR.glob("*.png"))


def _traits_filenames() -> list[str]:
    doc = json.loads((ROOT / "config" / "traits.json").read_text(encoding="utf-8"))
    layer = next(ly for ly in doc["layers"] if ly["name"] == "sky")
    return [t["sprite_filename"] for t in layer["traits"] if t.get("sprite_filename")]


@pytest.fixture(scope="module")
def plates() -> dict[str, Image.Image]:
    return {p.stem: Image.open(p).convert("RGBA") for p in PLATES}


# ------------------------------------------------------------- the contract


def test_renderer_keys_match_traits_json_exactly():
    assert set(sky.all_keys()) == {Path(f).stem for f in _traits_filenames()}


def test_every_declared_sky_file_exists():
    on_disk = {p.name for p in PLATES}
    assert set(_traits_filenames()) <= on_disk


def test_all_plates_are_2048_rgba(plates):
    for key, img in plates.items():
        assert img.size == (2048, 2048), key
        assert img.mode == "RGBA", key


def test_no_plate_is_empty(plates):
    """The defect this layer existed to fix: 15 byte-identical blank canvases."""
    for key, img in plates.items():
        assert alpha_stats(img)["max"] > 0.2, f"{key} is blank"


def test_all_plates_are_distinct(plates):
    digests = {key: img.tobytes() for key, img in plates.items()}
    assert len(set(digests.values())) == len(digests)


def test_alpha_ceiling_is_respected(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] <= sky.MAX_ALPHA + 0.01, key


def test_plates_stay_light_enough_to_layer_under(plates):
    """Mean alpha is the muddiness budget for everything stacked above."""
    for key, img in plates.items():
        assert alpha_stats(img)["mean"] <= 0.36, key


def test_plates_clear_the_waterline(plates):
    """Alpha must reach ~0 past HORIZON so the sea plate seats without a seam."""
    cut = int(2048 * (sky.HORIZON + 0.09))
    for key, img in plates.items():
        below = np.asarray(img)[cut:, :, 3]
        assert below.max() <= 2, f"{key} bleeds below the waterline"


def test_top_of_frame_carries_the_weather(plates):
    for key, img in plates.items():
        top = np.asarray(img)[:400, :, 3].astype(np.float32) / 255.0
        assert top.mean() > 0.05, f"{key} has an empty crown"


def test_plates_have_no_fully_opaque_regions(plates):
    """Nothing in an atmosphere layer should be a solid block except a disc."""
    for key, img in plates.items():
        assert alpha_stats(img)["opaque"] < 0.06, key


def test_plate_file_sizes_are_disciplined():
    """44,444 renders read these; a 3 MB plate is a pipeline cost, not detail."""
    for p in PLATES:
        assert p.stat().st_size < 1_600_000, f"{p.name} is {p.stat().st_size} bytes"


# --------------------------------------------------------------- the renderer


def test_specs_reference_only_master_palette_colors():
    pal = set(sky.PAL.values())
    for key, spec in sky.SKY_SPECS.items():
        for stop in spec.stops:
            assert tuple(stop) in pal, f"{key} uses an off-palette stop {stop}"
        assert spec.ink_color in sky.PAL, key


def test_spec_alpha_budgets_are_sane():
    for key, spec in sky.SKY_SPECS.items():
        assert 0.0 < spec.wash_peak <= sky.MAX_ALPHA, key
        assert 0.0 <= spec.line_alpha <= 1.0, key
        assert 0.0 <= spec.cloud_contrast <= 1.0, key


def test_render_is_deterministic():
    a = sky.render("fog", size=96).to_image().tobytes()
    b = sky.render("fog", size=96).to_image().tobytes()
    assert a == b


def test_render_rejects_unknown_trait():
    with pytest.raises(KeyError):
        sky.render("no_such_sky", size=64)


def test_render_honours_requested_size():
    assert sky.render("overcast", size=128).to_image().size == (128, 128)


def test_alpha_profile_peaks_at_top_and_dies_at_horizon():
    prof = sky._alpha_profile(256, 1.0)[:, 0]
    assert prof[0] == pytest.approx(prof.max(), abs=1e-6)
    assert prof[int(256 * (sky.HORIZON + 0.05))] == pytest.approx(0.0, abs=1e-6)
    assert prof[10] > prof[120]
