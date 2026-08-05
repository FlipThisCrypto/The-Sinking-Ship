# SPDX-License-Identifier: MIT
"""QA gates for the ship_condition overlay layer.

This layer's whole difficulty is that one sprite per condition must read
correctly over sixteen structurally unrelated ships. Most of these tests check
the devices that make that possible — the coordinate mapping, the occupancy
sampling, and the water geometry — rather than appearance.
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

from artgen import sea, ship_condition as sc  # noqa: E402
from artgen.core import alpha_stats  # noqa: E402

DIR = ROOT / "sprites" / "ship_condition"
PLATES = sorted(DIR.glob("*.png"))


def _traits_filenames() -> list[str]:
    doc = json.loads((ROOT / "config" / "traits.json").read_text(encoding="utf-8"))
    layer = next(ly for ly in doc["layers"] if ly["name"] == "ship_condition")
    return [t["sprite_filename"] for t in layer["traits"] if t.get("sprite_filename")]


@pytest.fixture(scope="module")
def plates() -> dict[str, Image.Image]:
    return {p.stem: Image.open(p).convert("RGBA") for p in PLATES}


# --------------------------------------------------------------- geometry


def test_layer_has_no_transform_in_render_config():
    """A transform would confine water to the ship's box and render a rectangle.

    The renderer compensates by mapping ship coordinates itself; if someone
    adds a transform here, every water condition gains a hard-edged box.
    """
    doc = json.loads((ROOT / "config" / "render.json").read_text(encoding="utf-8"))
    transforms = doc["profiles"]["illustration"]["layer_transforms"]
    assert "ship_condition" not in transforms


def test_ship_placement_is_read_from_config_not_hardcoded():
    doc = json.loads((ROOT / "config" / "render.json").read_text(encoding="utf-8"))
    tf = doc["profiles"]["illustration"]["layer_transforms"]["ship_class"]
    assert sc.ship_placement() == (float(tf["scale"]), float(tf["anchor_x"]),
                                   float(tf["anchor_y"]))


def test_ship_to_canvas_matches_the_compositor_placement():
    """Mirror of render_engine._place, including anchor_x.

    ship_class is anchored to one side of the frame, so a mapping that assumed
    horizontal centring would place every condition mark well off the hull.
    """
    scale, anchor_x, anchor_y = sc.ship_placement()
    size = 2048
    new = round(size * scale)
    ax = round(anchor_x * (size - new))
    ay = round(anchor_y * (size - new))
    for u, v in ((0.0, 0.0), (0.5, 0.5), (1.0, 1.0), (0.25, 0.7)):
        cx, cy = sc.ship_to_canvas(u, v)
        assert cx * size == pytest.approx(ax + u * new, abs=1.0)
        assert cy * size == pytest.approx(ay + v * new, abs=1.0)


def test_ship_is_not_horizontally_centred():
    """If it were, the character and the vessel would overlap into a tangle."""
    _, anchor_x, _ = sc.ship_placement()
    assert abs(anchor_x - 0.5) > 0.2


def test_sea_horizon_agrees_with_the_sea_layer():
    assert sc.SEA_HORIZON == sea.HORIZON


def test_waterline_in_ship_space_round_trips():
    v = sc.canvas_waterline_in_ship_space()
    assert sc.ship_to_canvas(0.5, v)[1] == pytest.approx(sc.SEA_HORIZON)
    assert 0.0 < v < 1.0


# ----------------------------------------------------------- occupancy field


def test_occupancy_is_a_probability_field_over_the_ship_plates():
    occ = sc.ship_occupancy()
    assert occ.shape == (512, 512)
    assert 0.0 <= occ.min() and occ.max() <= 1.0
    assert occ.max() > 0.6, "no region is common to most ships"


def test_sample_hull_lands_inside_the_ship_box():
    """Sampled points must map into the ship's composited rectangle."""
    scale, anchor_x, anchor_y = sc.ship_placement()
    lo_x = anchor_x * (1.0 - scale)
    hi_x = lo_x + scale
    lo_y = anchor_y * (1.0 - scale)
    ctx = sc.ConditionCtx(
        spec=sc.CONDITION_SPECS["burning"], size=1000,
        rng=np.random.default_rng(0), canvas=None, occ=sc.ship_occupancy(),
    )
    pts = ctx.sample_hull(200, y_range=(0.4, 0.8), min_occ=0.4)
    assert len(pts) == 200
    for x, y in pts:
        assert lo_x * 1000 - 1 <= x <= hi_x * 1000 + 1
        assert lo_y * 1000 - 1 <= y <= (lo_y + scale) * 1000 + 1


def test_sample_hull_respects_the_requested_vertical_band():
    ctx = sc.ConditionCtx(
        spec=sc.CONDITION_SPECS["burning"], size=1000,
        rng=np.random.default_rng(1), canvas=None, occ=sc.ship_occupancy(),
    )
    lo, hi = 0.45, 0.60
    pts = ctx.sample_hull(120, y_range=(lo, hi), min_occ=0.35)
    ys = [sc.ship_to_canvas(0.5, lo)[1] * 1000, sc.ship_to_canvas(0.5, hi)[1] * 1000]
    for _, y in pts:
        assert ys[0] - 3 <= y <= ys[1] + 3


def test_sample_hull_degrades_gracefully_when_nothing_qualifies():
    ctx = sc.ConditionCtx(
        spec=sc.CONDITION_SPECS["burning"], size=256,
        rng=np.random.default_rng(2), canvas=None, occ=sc.ship_occupancy(),
    )
    pts = ctx.sample_hull(5, y_range=(0.0, 0.01), min_occ=0.99)
    assert len(pts) == 5


# ------------------------------------------------------------------- water


def test_water_surface_relaxes_to_the_sea_horizon_at_the_frame_edges():
    """A raised local swell, not a second horizon contradicting the sea plate."""
    ctx = sc.ConditionCtx(
        spec=sc.CONDITION_SPECS["half_sunk"], size=512,
        rng=np.random.default_rng(0), canvas=None, occ=sc.ship_occupancy(),
    )
    surface = sc._surface_y(ctx, sc.CONDITION_SPECS["half_sunk"].water_level) / 512
    assert surface[0] == pytest.approx(sc.SEA_HORIZON, abs=0.02)
    # The swell is centred on the *vessel*, which is anchored off-centre, so
    # probe there rather than at the middle of the frame.
    ship_cx = int(sc.ship_to_canvas(0.5, 0.5)[0] * 512)
    assert surface[ship_cx] < sc.SEA_HORIZON - 0.05, "swell does not rise at the ship"
    far = 0 if ship_cx > 256 else 511
    assert surface[far] == pytest.approx(sc.SEA_HORIZON, abs=0.02)


def test_full_plane_water_ignores_the_swell():
    ctx = sc.ConditionCtx(
        spec=sc.CONDITION_SPECS["fully_underwater"], size=256,
        rng=np.random.default_rng(0), canvas=None, occ=sc.ship_occupancy(),
    )
    surface = sc._surface_y(ctx, 0.06) / 256
    assert surface.max() - surface.min() < 0.02


def test_listing_tilts_the_waterline():
    spec = sc.CONDITION_SPECS["listing"]
    assert spec.tilt != 0.0
    ctx = sc.ConditionCtx(spec=spec, size=512, rng=np.random.default_rng(0),
                          canvas=None, occ=sc.ship_occupancy())
    surface = sc._surface_y(ctx, spec.water_level)
    assert abs(surface[-1] - surface[0]) > 512 * 0.05


def test_submerged_water_lets_the_hull_read_through():
    """Opaque water would blot the ship out instead of sinking it."""
    for key in ("listing", "half_sunk", "fully_underwater"):
        assert sc.CONDITION_SPECS[key].water_alpha < 0.8, key


# ------------------------------------------------------------ shipped plates


def test_renderer_keys_match_traits_json_exactly():
    assert set(sc.all_keys()) == {Path(f).stem for f in _traits_filenames()}


def test_all_plates_are_2048_rgba(plates):
    for key, img in plates.items():
        assert img.size == (2048, 2048), key
        assert img.mode == "RGBA", key


def test_no_plate_is_empty(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] > 0.2, f"{key} is blank"


def test_all_plates_are_distinct(plates):
    assert len({img.tobytes() for img in plates.values()}) == len(plates)


def test_alpha_ceiling_is_respected(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] <= sc.MAX_ALPHA + 0.01, key


def test_no_condition_blankets_the_ship_it_marks(plates):
    """Mean alpha is the muddiness budget for the ship showing through.

    Coverage-at-2% is the wrong metric here: `ghost` is a wide soft aura that
    touches 59% of the frame while averaging 0.16 alpha, which is exactly what
    a spectral echo should be. What must stay bounded is how much light the
    overlay actually removes from the hull underneath.
    """
    for key, img in plates.items():
        assert alpha_stats(img)["mean"] <= 0.52, key


def test_hard_edged_damage_marks_stay_local(plates):
    """Rifts, spars and rigging mark a place; they must not cover the vessel."""
    marks = {"floating", "flooded", "broken_mast", "being_salvaged",
             "split_hull", "rebuilt", "burning"}
    for key in marks:
        assert alpha_stats(plates[key])["coverage"] < 0.30, key


def test_water_conditions_reach_both_frame_edges(plates):
    """The rectangle bug: water confined to the ship's box shows hard sides."""
    for key in ("listing", "half_sunk", "fully_underwater"):
        a = np.asarray(plates[key])[:, :, 3]
        row = int(2048 * 0.92)
        assert a[row, 2] > 8, f"{key} leaves the left edge dry"
        assert a[row, -3] > 8, f"{key} leaves the right edge dry"


def test_plate_file_sizes_are_disciplined():
    for p in PLATES:
        assert p.stat().st_size < 1_600_000, f"{p.name} is {p.stat().st_size} bytes"


def test_render_is_deterministic():
    a = sc.render("split_hull", size=96).to_image().tobytes()
    b = sc.render("split_hull", size=96).to_image().tobytes()
    assert a == b


def test_render_rejects_unknown_trait():
    with pytest.raises(KeyError):
        sc.render("no_such_condition", size=64)
