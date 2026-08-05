# SPDX-License-Identifier: MIT
"""QA gates for the eyes layer.

The eyes plate is authored in canonical rig space and lands on each body via
``render_engine._place_face``, so the assertions split in two: that the plate
agrees with the rig it was drawn against, and that it *occludes* the eye already
drawn on the body rather than floating over it.
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


def test_eye_anchor_matches_the_canonical_rig():
    """If these drift apart, every eye plate lands off the head."""
    assert eyes.EYE == (rig.CANONICAL.eye_x, rig.CANONICAL.eye_y)


def test_every_plate_is_centred_on_the_rig_anchor(plates):
    """The drawn eye's centre of mass must sit on the anchor the rig expects."""
    for key, img in plates.items():
        # Measure the opaque eye body only. `crying` and `laser` deliberately
        # spill past it — tears fall, a beam leaves — and averaging those in
        # drags the centroid off the anchor.
        a = np.asarray(img)[:, :, 3]
        ys, xs = np.nonzero(a >= 250)
        assert xs.size, key
        cx = float(xs.mean()) / img.width
        cy = float(ys.mean()) / img.height
        assert cx == pytest.approx(eyes.EYE[0], abs=0.02), f"{key} x={cx:.3f}"
        assert cy == pytest.approx(eyes.EYE[1], abs=0.02), f"{key} y={cy:.3f}"


def test_plates_stay_inside_the_head(plates):
    """Nothing may stray far from the canonical head, or it lands on the body."""
    head_top = rig.CANONICAL.eye_y - rig.CANONICAL.head_h
    head_bottom = rig.CANONICAL.eye_y + rig.CANONICAL.head_h * 1.6
    for key, img in plates.items():
        a = np.asarray(img)[:, :, 3]
        ys, xs = np.nonzero(a > 20)
        assert ys.min() / img.height > head_top, key
        assert ys.max() / img.height < head_bottom, f"{key} reaches the body"


def test_the_drawn_eye_matches_the_canonical_eye_width():
    """The art and the rig must agree on how wide the canonical eye is.

    The compositor scales each plate by ``anchor.eye_w / canonical.eye_w``, so
    art drawn at a different size than the rig claims lands at the wrong scale
    on every body. This is what went wrong when the layer scaled by head
    height: eye-to-head ratio varies by more than 2x across the plates.
    """
    assert eyes.EYE_W * 2 == pytest.approx(rig.CANONICAL.eye_w, abs=1e-6)
    assert 0.6 < eyes.EYE_H / eyes.EYE_W < 1.0, "eye aspect should be wider than tall"


@pytest.mark.parametrize("key", ["normal", "closed", "sleepy", "dead"])
def test_the_eye_body_is_opaque(key, plates):
    """A translucent sclera would let the body's own eye show through.

    `closed` matters most: a see-through lid renders an open eye with a lid
    floating over it.
    """
    img = plates[key]
    cx, cy = int(eyes.EYE[0] * 2048), int(eyes.EYE[1] * 2048)
    r = int(eyes.EYE_H * 2048 * 0.35)
    core = np.asarray(img)[cy - r:cy + r, cx - r:cx + r, 3]
    assert core.min() >= 250, f"{key} eye body is not opaque"


def plate_of(key: str) -> Image.Image:
    return Image.open(DIR / f"{key}.png").convert("RGBA")


def test_the_occluding_cover_does_not_shrink_with_the_lid():
    """A shut eye must still cover the whole eye drawn on the body.

    Conflating the occluding shape with the visible opening left the body's
    open eye showing around a sliver of lid.
    """
    opaque = {}
    for key in ("normal", "closed"):
        a = np.asarray(plate_of(key))[:, :, 3]
        opaque[key] = int((a >= 250).sum())
    assert opaque["closed"] >= opaque["normal"] * 0.85


def test_closed_and_open_eyes_differ_in_colour_not_coverage(plates):
    """They share an occluding cover by design, so alpha is nearly identical.

    What separates them is what is inked onto it: an iris and pupil versus a
    lid line and lashes.
    """
    # Compare inside the eye region: the plate is mostly empty canvas, so a
    # whole-image mean just measures how small the eye is.
    cx, cy = int(eyes.EYE[0] * 2048), int(eyes.EYE[1] * 2048)
    r = int(eyes.EYE_W * 2048 * 1.4)
    box = (slice(cy - r, cy + r), slice(cx - r, cx + r))
    a = np.asarray(plates["closed"]).astype(np.int16)[box]
    b = np.asarray(plates["normal"]).astype(np.int16)[box]
    alpha_delta = np.abs(a[:, :, 3] - b[:, :, 3]).mean()
    rgb_delta = np.abs(a[:, :, :3] - b[:, :, :3]).mean()
    assert alpha_delta < 12.0, "coverage should barely differ"
    assert rgb_delta > 15.0, "the inked state should differ"


# --------------------------------------------------------- placement on bodies


@pytest.mark.parametrize("plate", ["green_standing", "chrome_saluting",
                                   "blue_standing", "ghost_sitting"])
def test_eye_lands_on_the_head_of_representative_bodies(plate):
    """End-to-end: the plate, through the rig, onto a body's head."""
    size = 512
    btf = json.loads(
        (ROOT / "config" / "render.json").read_text(encoding="utf-8")
    )["profiles"]["illustration"]["layer_transforms"]["body"]
    sprite = eyes.render("normal", size=size).to_image()
    placed = re_._place_face(sprite, size, RIG["plates"][plate], RIG["canonical"], btf)
    a = np.asarray(placed)[:, :, 3]
    ys, xs = np.nonzero(a > 128)
    assert xs.size, plate
    anchor = RIG["plates"][plate]
    sc, ay = float(btf["scale"]), float(btf["anchor_y"])
    want_x = anchor["eye_x"] * sc + (1.0 - sc) / 2.0
    want_y = anchor["eye_y"] * sc + ay * (1.0 - sc)
    assert float(xs.mean()) / size == pytest.approx(want_x, abs=0.03), plate
    assert float(ys.mean()) / size == pytest.approx(want_y, abs=0.03), plate


# --------------------------------------------------------------- the renderer


def test_specs_reference_only_master_palette_colors():
    for key, spec in eyes.EYE_SPECS.items():
        assert spec.iris in eyes.PAL, f"{key} iris {spec.iris}"


def test_spec_budgets_are_sane():
    for key, spec in eyes.EYE_SPECS.items():
        assert 0.0 <= spec.open_amount <= 1.4, key
        assert 0.0 < spec.pupil < 1.0, key
        assert 0.0 < spec.line_alpha <= 1.0, key


def test_exactly_one_trait_is_fully_closed():
    shut = [k for k, s in eyes.EYE_SPECS.items() if s.open_amount < 0.12]
    assert shut == ["closed"]


def test_render_is_deterministic():
    a = eyes.render("crying", size=128).to_image().tobytes()
    b = eyes.render("crying", size=128).to_image().tobytes()
    assert a == b


def test_render_rejects_unknown_trait():
    with pytest.raises(KeyError):
        eyes.render("no_such_eye", size=64)


def test_plate_file_sizes_are_small():
    """A single eye covers a fraction of the canvas; these must stay tiny."""
    for p in PLATES:
        assert p.stat().st_size < 200_000, f"{p.name} is {p.stat().st_size} bytes"
