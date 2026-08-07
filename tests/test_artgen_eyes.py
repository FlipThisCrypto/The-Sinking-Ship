# SPDX-License-Identifier: MIT
"""QA gates for the eyes layer.

This layer draws the **pupil** and, where the expression needs it, a lid or an
accent. It does not draw an eyeball: the body plates keep their own iris,
sclera, eyelid and socket, and only their pupil is removed
(``artgen.repair.blank_pupil``). An earlier version drew a complete opaque
eyeball over the top and read as a decal — a constructed shape sitting on a
hand-drawn face — so several of these tests exist to keep it from growing back.
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

import render_engine as re_  # noqa: E402
from artgen import eyes, rig  # noqa: E402
from artgen.core import alpha_stats  # noqa: E402

DIR = ROOT / "sprites" / "eyes"
PLATES = sorted(DIR.glob("*.png"))
RIG = json.loads((ROOT / "config" / "rig.json").read_text(encoding="utf-8"))
BODY_TF = json.loads(
    (ROOT / "config" / "render.json").read_text(encoding="utf-8")
)["profiles"]["illustration"]["layer_transforms"]["body"]


def _traits_filenames() -> list[str]:
    doc = json.loads((ROOT / "config" / "traits.json").read_text(encoding="utf-8"))
    layer = next(ly for ly in doc["layers"] if ly["name"] == "eyes")
    return [t["sprite_filename"] for t in layer["traits"] if t.get("sprite_filename")]


@pytest.fixture(scope="module")
def plates() -> dict[str, Image.Image]:
    return {p.stem: Image.open(p).convert("RGBA") for p in PLATES}


# ------------------------------------------------------------- the contract


def test_renderer_keys_match_traits_json_exactly():
    assert set(eyes.all_keys()) == {Path(f).stem for f in _traits_filenames()}
    assert len(eyes.all_keys()) == 16


def test_all_plates_are_2048_rgba(plates):
    for key, img in plates.items():
        assert img.size == (2048, 2048), key
        assert img.mode == "RGBA", key


def test_no_plate_is_empty(plates):
    for key, img in plates.items():
        assert alpha_stats(img)["max"] > 0.9, f"{key} is blank"


def test_all_plates_are_distinct(plates):
    assert len({img.tobytes() for img in plates.values()}) == len(plates)


# ------------------------------------------------------------------ the rig


def test_eye_anchor_and_width_match_the_canonical_rig():
    """If the art and the rig disagree, every plate lands wrong on every body.

    The compositor scales by ``anchor.eye_w / canonical.eye_w``, so the width
    this layer is drawn against has to be the width the rig publishes.
    """
    assert eyes.EYE == (rig.CANONICAL.eye_x, rig.CANONICAL.eye_y)
    assert eyes.EYE_W == pytest.approx(rig.CANONICAL.eye_w, abs=1e-9)


def test_the_pupil_fits_inside_the_area_the_body_blanked():
    """blank_pupil clears 0.34 * eye_w; drawing past that lands on the artist's
    iris and the composite shows both."""
    cleared = 0.34 * eyes.EYE_W
    widest = max(s.pupil_scale for s in eyes.EYE_SPECS.values())
    assert eyes.PUPIL_R * widest < cleared, (
        f"pupil {eyes.PUPIL_R * widest:.4f} exceeds cleared {cleared:.4f}"
    )


def test_every_plate_is_centred_on_the_rig_anchor(plates):
    for key, img in plates.items():
        a = np.asarray(img)[:, :, 3]
        ys, xs = np.nonzero(a >= 250)
        assert xs.size, key
        assert float(xs.mean()) / img.width == pytest.approx(eyes.EYE[0], abs=0.03), key


def test_plates_stay_within_the_eye_and_its_immediate_surround(plates):
    """Nothing may stray far from the eye, or it lands on the body.

    `crying` and `laser` deliberately reach past the eye — tears fall, a beam
    leaves — so the bound is generous, but finite.
    """
    for key, img in plates.items():
        a = np.asarray(img)[:, :, 3]
        ys, xs = np.nonzero(a > 20)
        reach = max(
            abs(xs.min() / img.width - eyes.EYE[0]),
            abs(xs.max() / img.width - eyes.EYE[0]),
            abs(ys.min() / img.height - eyes.EYE[1]),
            abs(ys.max() / img.height - eyes.EYE[1]),
        )
        assert reach < eyes.EYE_W * 4.0, f"{key} reaches {reach:.3f} from the eye"


# ------------------------------------------- pupil, not a replacement eyeball


def test_no_plate_paints_a_whole_eyeball(plates):
    """The regression this layer was rebuilt to remove.

    An opaque disc the size of the eye would cover the artist's iris. Coverage
    is measured against the eye's own area, so it scales with the rig rather
    than with the canvas. Lid traits are exempt: a lid is *meant* to cover.
    """
    size = 2048
    eye_area = np.pi * (eyes.EYE_W * 0.5 * size) ** 2
    for key, img in plates.items():
        if eyes.EYE_SPECS[key].lid > 0.01:
            continue
        opaque = int((np.asarray(img)[:, :, 3] >= 250).sum())
        assert opaque < eye_area * 0.85, (
            f"{key} covers {opaque / eye_area:.2f} of the eye — drawing an eyeball"
        )


def test_the_pupil_itself_is_opaque(plates):
    """Whatever its shape, the pupil must read as solid against the iris."""
    for key in ("normal", "hopeful", "looking_to_horizon", "heart", "diamond"):
        a = np.asarray(plates[key])[:, :, 3]
        ys, xs = np.nonzero(a >= 250)
        assert xs.size, key
        # Solidity as fill ratio within the pupil's own bounding box, not the
        # alpha at one chosen point: a heart has a cleft and a diamond has
        # corners, so a geometric probe lands in empty space on some shapes.
        box = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        fill = float((box >= 250).mean())
        assert fill > 0.45, f"{key} pupil is not solid (fill {fill:.2f})"


def test_closed_is_the_only_trait_without_a_pupil():
    shut = [k for k, s in eyes.EYE_SPECS.items() if s.lid >= 0.99]
    assert shut == ["closed"]


def test_closed_covers_more_of_the_eye_than_an_open_one(plates):
    a = int((np.asarray(plates["closed"])[:, :, 3] >= 200).sum())
    b = int((np.asarray(plates["normal"])[:, :, 3] >= 200).sum())
    assert a > b * 2, "a shut lid must cover far more than a pupil"


# --------------------------------------------------------- placement on bodies


@pytest.mark.parametrize("plate", ["green_standing", "chrome_saluting",
                                   "blue_standing", "ghost_sitting",
                                   "gold_on_bow", "corrupted_sitting"])
def test_pupil_lands_on_the_eye_of_representative_bodies(plate):
    """End-to-end: the plate, through the rig, onto a body's own eye."""
    size = 512
    sprite = eyes.render("normal", size=size).to_image()
    placed = re_._place_face(sprite, size, RIG["plates"][plate],
                             RIG["canonical"], BODY_TF, "eye_w")
    a = np.asarray(placed)[:, :, 3]
    ys, xs = np.nonzero(a > 128)
    assert xs.size, plate
    anchor = RIG["plates"][plate]
    sc = float(BODY_TF["scale"])
    ax = float(BODY_TF.get("anchor_x", 0.5))
    ay = float(BODY_TF["anchor_y"])
    want_x = anchor["eye_x"] * sc + ax * (1.0 - sc)
    want_y = anchor["eye_y"] * sc + ay * (1.0 - sc)
    assert float(xs.mean()) / size == pytest.approx(want_x, abs=0.02), plate
    assert float(ys.mean()) / size == pytest.approx(want_y, abs=0.02), plate


@pytest.mark.parametrize("plate", ["green_standing", "chrome_standing",
                                   "blue_sitting"])
def test_the_placed_pupil_is_no_wider_than_the_body_eye(plate):
    """A pupil wider than the eye it sits in would spill onto the face."""
    size = 1024
    sprite = eyes.render("normal", size=size).to_image()
    placed = re_._place_face(sprite, size, RIG["plates"][plate],
                             RIG["canonical"], BODY_TF, "eye_w")
    xs = np.nonzero(np.asarray(placed)[:, :, 3] > 128)[1]
    drawn = (xs.max() - xs.min()) / size
    eye_on_canvas = RIG["plates"][plate]["eye_w"] * float(BODY_TF["scale"])
    assert drawn < eye_on_canvas, (
        f"{plate}: pupil {drawn:.4f} wider than eye {eye_on_canvas:.4f}"
    )


# --------------------------------------------------------------- the renderer


def test_specs_reference_only_master_palette_colors():
    for key, spec in eyes.EYE_SPECS.items():
        assert spec.colour in eyes.PAL, f"{key} colour {spec.colour}"
        glow = spec.extras.get("glow")
        if glow:
            assert glow in eyes.PAL, f"{key} glow {glow}"


def test_spec_budgets_are_sane():
    for key, spec in eyes.EYE_SPECS.items():
        assert 0.0 <= spec.lid <= 1.0, key
        assert 0.3 <= spec.pupil_scale <= 1.5, key
        assert 0.0 <= spec.highlight <= 1.0, key


def test_render_is_deterministic():
    a = eyes.render("crying", size=128).to_image().tobytes()
    b = eyes.render("crying", size=128).to_image().tobytes()
    assert a == b


def test_render_rejects_unknown_trait():
    with pytest.raises(KeyError):
        eyes.render("no_such_eye", size=64)


def test_plate_file_sizes_are_small():
    """A pupil covers a tiny fraction of the canvas; these must stay tiny."""
    for p in PLATES:
        assert p.stat().st_size < 120_000, f"{p.name} is {p.stat().st_size} bytes"
