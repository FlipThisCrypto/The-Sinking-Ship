# SPDX-License-Identifier: MIT
"""Tests for the body rig and the compositor's face-layer registration.

``eyes``, ``mouth`` and ``hat`` are single sprites per trait, but the head moves
a long way between body plates — eye centres span x 0.26 to x 0.83 and head
height varies about 2.4x. Without the rig those sprites land on the cheek, or
off the head entirely, depending on the roll. These tests pin the arithmetic
that prevents that.
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
from artgen import body, rig  # noqa: E402

DOC = json.loads((ROOT / "config" / "rig.json").read_text(encoding="utf-8"))
BODY_TF = json.loads(
    (ROOT / "config" / "render.json").read_text(encoding="utf-8")
)["profiles"]["illustration"]["layer_transforms"]["body"]


@pytest.fixture(scope="module")
def palette():
    return re_.Palette()


@pytest.fixture(scope="module")
def profile():
    return re_.load_profile(None)


# ----------------------------------------------------------------- the table


def test_rig_json_matches_the_module():
    """config/rig.json is generated; a hand edit that drifts is a silent bug."""
    assert DOC == rig.build_doc()


def test_every_body_plate_has_an_anchor():
    assert set(DOC["plates"]) == set(body.all_keys())
    assert len(DOC["plates"]) == 48


def test_annotations_cover_every_unique_source():
    assert set(rig.ANNOTATIONS) == {body.source_for(k) for k in body.all_keys()}
    assert len(rig.ANNOTATIONS) == 12


def test_plates_inherit_the_anchor_of_their_source():
    anchors = rig.plate_anchors()
    for key in body.all_keys():
        assert anchors[key] == rig.ANNOTATIONS[body.source_for(key)], key


def test_anchor_values_are_in_range():
    for name, a in rig.ANNOTATIONS.items():
        assert 0.0 < a.eye_x < 1.0, name
        assert 0.0 < a.eye_y < 1.0, name
        assert 0.05 < a.head_h < 0.6, name
        assert 0.02 < a.eye_w < 0.20, name
        assert a.eye_w < a.head_h, f"{name}: the eye cannot exceed the head"
        assert a.facing in ("left", "right"), name


def test_face_layers_are_the_head_following_ones():
    """clothing keys off the torso, so it must not be dragged onto the head."""
    assert set(DOC["face_layers"]) == {"eyes", "mouth", "hat"}
    assert "clothing" not in DOC["face_layers"]
    assert "body" not in DOC["face_layers"]


def test_rig_is_not_part_of_the_fairness_bundle_hash():
    """Rendering config must not perturb the traits/weights/tiers hash."""
    from shipgen.config import GenConfig

    cfg = GenConfig()
    before = cfg.config_hash
    assert before is None or isinstance(before, str)
    # rig.json is not among the documents the bundle hash is built from
    src = (ROOT / "engine" / "shipgen" / "config.py").read_text(encoding="utf-8")
    bundle = src[src.index("config_bundle_hash("):src.index("config_bundle_hash(") + 300]
    assert "rig" not in bundle


# ------------------------------------------------------------- the transform


def test_canonical_anchor_is_the_identity_transform():
    scale, dx, dy, mirror = rig.face_transform(rig.CANONICAL)
    assert scale == pytest.approx(1.0)
    assert dx == pytest.approx(0.0)
    assert dy == pytest.approx(0.0)
    assert mirror is False


def test_transform_maps_the_canonical_eye_onto_the_anchor_eye():
    for name, a in rig.ANNOTATIONS.items():
        scale, dx, dy, mirror = rig.face_transform(a)
        cx = 1.0 - rig.CANONICAL.eye_x if mirror else rig.CANONICAL.eye_x
        assert cx * scale + dx == pytest.approx(a.eye_x, abs=1e-9), name
        assert rig.CANONICAL.eye_y * scale + dy == pytest.approx(a.eye_y, abs=1e-9), name


def test_features_scale_by_eye_width_and_hats_by_head_height():
    """One measure cannot serve both: eye-to-head ratio varies by >2x here.

    gold has a 0.042 eye on a 0.200 head; blue_back_turned has a 0.090 eye on a
    0.170 head. Scaling eye art by head height made it far too large on the
    former and too small on the latter.
    """
    for name, a in rig.ANNOTATIONS.items():
        by_eye = rig.face_transform(a, scale_by="eye_w")[0]
        by_head = rig.face_transform(a, scale_by="head_h")[0]
        assert by_eye == pytest.approx(a.eye_w / rig.CANONICAL.eye_w), name
        assert by_head == pytest.approx(a.head_h / rig.CANONICAL.head_h), name
    assert DOC["face_layers"] == {"eyes": "eye_w", "mouth": "eye_w",
                                  "hat": "head_h"}


def test_eye_and_head_scales_genuinely_disagree():
    """If they agreed, the distinction above would be dead weight."""
    worst = max(
        abs(rig.face_transform(a, scale_by="eye_w")[0]
            - rig.face_transform(a, scale_by="head_h")[0])
        for a in rig.ANNOTATIONS.values()
    )
    assert worst > 0.5


def test_only_the_left_facing_plate_is_mirrored():
    mirrored = {n for n, a in rig.ANNOTATIONS.items()
                if rig.face_transform(a)[3]}
    assert mirrored == {n for n, a in rig.ANNOTATIONS.items() if a.facing == "left"}
    assert mirrored, "expected at least one left-facing plate"


def test_no_plate_needs_an_extreme_scale():
    """The canonical rig sits mid-distribution so transforms stay modest."""
    scales = [rig.face_transform(a)[0] for a in rig.ANNOTATIONS.values()]
    assert min(scales) > 0.5
    assert max(scales) < 2.0


# ------------------------------------------------- compositor placement maths


def _marker_sprite(size: int, at: tuple[float, float]) -> Image.Image:
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    x, y = int(at[0] * size), int(at[1] * size)
    arr[y - 1:y + 2, x - 1:x + 2] = (255, 0, 0, 255)
    return Image.fromarray(arr, mode="RGBA")


def _found_at(img: Image.Image) -> tuple[float, float]:
    a = np.asarray(img)[:, :, 3]
    ys, xs = np.nonzero(a > 80)
    assert xs.size, "marker vanished"
    return float(xs.mean()) / img.width, float(ys.mean()) / img.height


@pytest.mark.parametrize("plate", sorted(DOC["plates"]))
def test_face_sprite_lands_on_the_head_of_every_body(plate):
    """The whole point: a sprite authored at the canonical eye must land on
    this body's eye, after *both* the rig and the body's own layer transform."""
    size = 512
    sprite = _marker_sprite(size, (rig.CANONICAL.eye_x, rig.CANONICAL.eye_y))
    placed = re_._place_face(sprite, size, DOC["plates"][plate],
                             DOC["canonical"], BODY_TF)
    anchor = DOC["plates"][plate]
    sc = float(BODY_TF["scale"])
    anchor_y = float(BODY_TF["anchor_y"])
    want_x = anchor["eye_x"] * sc + (1.0 - sc) / 2.0
    want_y = anchor["eye_y"] * sc + anchor_y * (1.0 - sc)
    got_x, got_y = _found_at(placed)
    assert got_x == pytest.approx(want_x, abs=0.01), plate
    assert got_y == pytest.approx(want_y, abs=0.01), plate


def test_place_face_without_a_body_transform_is_the_plain_rig():
    size = 256
    sprite = _marker_sprite(size, (rig.CANONICAL.eye_x, rig.CANONICAL.eye_y))
    anchor = DOC["plates"]["green_standing"]
    placed = re_._place_face(sprite, size, anchor, DOC["canonical"], None)
    got_x, got_y = _found_at(placed)
    assert got_x == pytest.approx(anchor["eye_x"], abs=0.01)
    assert got_y == pytest.approx(anchor["eye_y"], abs=0.01)


def test_mirrored_body_flips_the_sprite():
    """A profile eye must stay on the correct side of the skull."""
    size = 256
    # Offset from the eye rather than far across the plate: the left-facing
    # body has the largest head in the set, so its transform scales ~1.7x and a
    # distant marker would be pushed off-canvas.
    mark_x = rig.CANONICAL.eye_x - 0.06
    sprite = _marker_sprite(size, (mark_x, rig.CANONICAL.eye_y))
    left = next(n for n, a in rig.ANNOTATIONS.items() if a.facing == "left")
    plate = next(k for k in body.all_keys() if body.source_for(k) == left)
    placed = re_._place_face(sprite, size, DOC["plates"][plate], DOC["canonical"], None)
    got_x, _ = _found_at(placed)
    anchor = DOC["plates"][plate]
    scale = anchor["eye_w"] / DOC["canonical"]["eye_w"]
    mirrored = 1.0 - mark_x
    expected = anchor["eye_x"] + (mirrored - (1.0 - DOC["canonical"]["eye_x"])) * scale
    assert got_x == pytest.approx(expected, abs=0.02)
    # and it must land on the opposite side of the anchor from where it started
    assert got_x > anchor["eye_x"]


# ------------------------------------------------------------- the compositor


def test_compositor_loads_the_rig():
    doc = re_._rig_doc()
    assert doc is not None
    assert set(doc["face_layers"]) == {"eyes", "mouth", "hat"}


def test_compositor_resolves_the_body_plate_from_traits(cfg, palette, profile):
    store = re_.SpriteStore(cfg, palette, profile, ROOT / "sprites")
    traits = {
        "sky": "Calm Blue", "sea": "Calm", "scene_element": "None",
        "ship_class": "Raft", "ship_condition": "Floating", "body": "Gold",
        "pose": "Sitting", "clothing": "Hoodie", "eyes": "Normal",
        "mouth": "None", "hat": "None", "aura": "None",
    }
    assert re_._body_plate(store, traits) == "gold_sitting"


def test_compose_still_produces_a_master_canvas(cfg, palette, profile):
    from conftest import COIN_A, TEST_SALT
    from shipgen.roll import RollEngine, derive_placements

    engine = RollEngine(cfg)
    manifest = engine.roll_chest(
        TEST_SALT, COIN_A, "castaway", 1, 1,
        derive_placements(TEST_SALT, cfg), "prov-rig-test",
    )
    entry = next(e for e in manifest["nfts"] if e["type"] == "generated")
    store = re_.SpriteStore(cfg, palette, profile, ROOT / "sprites")
    img = re_.compose(store, entry["traits"], entry.get("depth_zone"))
    assert img.size == (profile.master_px, profile.master_px)
    assert img.mode == "RGBA"
