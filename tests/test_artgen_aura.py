# SPDX-License-Identifier: MIT
"""QA gates for the aura layer.

Aura is composited last, over eyes, mouth and hat. Its defining risk is
therefore not that it looks weak but that it buries the face that carries the
character's expression — so most of these tests police the face guard and the
ring-shaped emission that keeps the portrait readable.
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

from artgen import aura  # noqa: E402
from artgen.core import alpha_stats  # noqa: E402

DIR = ROOT / "sprites" / "aura"
PLATES = sorted(DIR.glob("*.png"))


def _traits_filenames() -> list[str]:
    doc = json.loads((ROOT / "config" / "traits.json").read_text(encoding="utf-8"))
    layer = next(ly for ly in doc["layers"] if ly["name"] == "aura")
    return [t["sprite_filename"] for t in layer["traits"] if t.get("sprite_filename")]


@pytest.fixture(scope="module")
def plates() -> dict[str, Image.Image]:
    return {p.stem: Image.open(p).convert("RGBA") for p in PLATES}


def _face_box(size: int = 2048) -> tuple[int, int, int, int]:
    cx, cy = aura.FOCUS[0] * size, aura.FOCUS[1] * size
    rx, ry = aura.FACE_GUARD[0] * size * 0.5, aura.FACE_GUARD[1] * size * 0.5
    return (int(cx - rx), int(cy - ry), int(cx + rx), int(cy + ry))


# ------------------------------------------------------------- the contract


def test_renderer_keys_match_traits_json_exactly():
    assert set(aura.all_keys()) == {Path(f).stem for f in _traits_filenames()}


def test_aura_is_the_topmost_layer():
    """The face guard only matters because nothing composites after this."""
    doc = json.loads((ROOT / "config" / "traits.json").read_text(encoding="utf-8"))
    orders = {ly["name"]: ly["z_order"] for ly in doc["layers"]
              if ly.get("z_order") is not None}
    assert orders["aura"] == max(orders.values())


def test_all_plates_are_2048_rgba(plates):
    for key, img in plates.items():
        assert img.size == (2048, 2048), key
        assert img.mode == "RGBA", key


def test_no_plate_is_empty(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] > 0.25, f"{key} is blank"


def test_all_plates_are_distinct(plates):
    assert len({img.tobytes() for img in plates.values()}) == len(plates)


def test_alpha_ceiling_is_respected(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] <= aura.MAX_ALPHA + 0.01, key


# --------------------------------------------------------------- face guard


def test_face_guard_attenuates_the_centre_and_releases_outside():
    guard = aura.face_guard_mask(512, aura.FACE_GUARD_KEEP)
    cx, cy = int(aura.FOCUS[0] * 512), int(aura.FOCUS[1] * 512)
    assert guard[cy, cx] == pytest.approx(aura.FACE_GUARD_KEEP, abs=1e-5)
    assert guard[10, 10] == pytest.approx(1.0, abs=1e-5)
    assert guard.min() >= aura.FACE_GUARD_KEEP - 1e-6
    assert guard.max() <= 1.0 + 1e-6


def test_face_guard_is_monotonic_outward():
    guard = aura.face_guard_mask(512, 0.3)
    cy = int(aura.FOCUS[1] * 512)
    cx = int(aura.FOCUS[0] * 512)
    row = guard[cy, cx:]
    assert np.all(np.diff(row) >= -1e-6)


def test_every_plate_keeps_the_face_readable(plates):
    """The whole point of the layer's construction.

    Aura draws over the eyes and mouth; if it goes opaque there, the character
    is gone. `laser_bloom` is allowed more because its beam is *meant* to cross
    the eye line.
    """
    x0, y0, x1, y1 = _face_box()
    for key, img in plates.items():
        face = np.asarray(img)[y0:y1, x0:x1, 3].astype(np.float32) / 255.0
        limit = 0.62 if key == "laser_bloom" else 0.50
        assert face.mean() < limit, f"{key} buries the face (mean {face.mean():.2f})"


RIM_LIGHT = ("green_magic_glow", "purple_magic_glow", "ghost_fade",
             "golden_radiance", "chia_bloom")
"""Traits whose emission is meant to wrap the figure rather than cross it.

`halo_light` and `laser_bloom` are excluded on purpose — a halo spills down
onto the face and the laser is *aimed* along the eye line. `crystal_shimmer`
and `corruption_static` scatter across the frame, so neither pattern applies.
"""


@pytest.mark.parametrize("key", RIM_LIGHT)
def test_rim_light_traits_are_lighter_over_the_face_than_around_it(key, plates):
    """Measured ratios run 0.31-0.67; anything above 1 is a filter, not rim light."""
    size = 2048
    cx, cy = aura.FOCUS[0] * size, aura.FOCUS[1] * size
    rx, ry = aura.FACE_GUARD[0] * size * 0.5, aura.FACE_GUARD[1] * size * 0.5
    ys, xs = np.mgrid[0:size, 0:size]
    face = (((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2) <= 1.0
    a = np.asarray(plates[key])[:, :, 3].astype(np.float32) / 255.0
    assert a[face].mean() < a[~face].mean() * 0.85, key


def test_no_plate_goes_opaque_over_the_face(plates):
    """Whatever the pattern, the aura must never fully occlude the features."""
    x0, y0, x1, y1 = _face_box()
    for key, img in plates.items():
        face = np.asarray(img)[y0:y1, x0:x1, 3].astype(np.float32) / 255.0
        assert face.max() <= aura.MAX_ALPHA + 0.01, key
        assert (face > 0.85).mean() < 0.06, f"{key} is near-opaque over the face"


def test_spec_guards_are_in_range():
    for key, spec in aura.AURA_SPECS.items():
        assert 0.0 < spec.guard <= 1.0, key
        assert 0.0 < spec.bloom <= 1.0, key


def test_specs_reference_only_master_palette_colors():
    pal = set(aura.PAL.values())
    for key, spec in aura.AURA_SPECS.items():
        for col in spec.colors:
            assert tuple(col) in pal, f"{key} uses an off-palette colour {col}"
        assert spec.ink_color in aura.PAL, key


# ------------------------------------------------------------------ helpers


def test_ring_peaks_at_its_radius_not_at_the_centre():
    ctx = aura.AuraCtx(spec=aura.AURA_SPECS["chia_bloom"], size=256,
                       rng=np.random.default_rng(0), canvas=None)
    r = 0.25
    ring = ctx.ring(aura.TORSO, r, 0.08)
    cx, cy = int(aura.TORSO[0] * 256), int(aura.TORSO[1] * 256)
    at_centre = ring[cy, cx]
    at_radius = ring[cy, min(255, cx + int(r * 256))]
    assert at_radius > at_centre * 3


def test_radial_falls_to_zero_at_its_radius():
    ctx = aura.AuraCtx(spec=aura.AURA_SPECS["chia_bloom"], size=256,
                       rng=np.random.default_rng(0), canvas=None)
    rad = ctx.radial(aura.TORSO, 0.2)
    cx, cy = int(aura.TORSO[0] * 256), int(aura.TORSO[1] * 256)
    # The nominal centre lands between pixels, so the sampled peak is just
    # under 1: at falloff 2 a half-pixel offset costs ~2%.
    assert 0.97 < rad.max() <= 1.0
    assert rad[cy, cx] > 0.97
    assert rad[cy, min(255, cx + int(0.2 * 256) + 2)] == pytest.approx(0.0, abs=1e-5)
    # monotone outward along the row
    row = rad[cy, cx:]
    assert np.all(np.diff(row) <= 1e-6)


def test_plate_file_sizes_are_disciplined():
    for p in PLATES:
        assert p.stat().st_size < 1_600_000, f"{p.name} is {p.stat().st_size} bytes"


def test_render_is_deterministic():
    a = aura.render("halo_light", size=96).to_image().tobytes()
    b = aura.render("halo_light", size=96).to_image().tobytes()
    assert a == b


def test_render_rejects_unknown_trait():
    with pytest.raises(KeyError):
        aura.render("no_such_aura", size=64)
