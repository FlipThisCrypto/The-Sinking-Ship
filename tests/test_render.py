# SPDX-License-Identifier: MIT
"""Render pipeline guards: sprite inventory and deterministic compose smoke."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from conftest import TEST_SALT, COIN_A
from render_engine import Palette, SpriteStore, compose, load_profile, resize_to, validate_sprites
from shipgen.roll import RollEngine, derive_placements

REPO = Path(__file__).resolve().parent.parent
SPRITES = REPO / "sprites"


@pytest.fixture(scope="module")
def profile():
    return load_profile(None)


@pytest.fixture(scope="module")
def palette():
    return Palette()


def test_illustration_sprites_validate_clean(cfg, palette, profile):
    """Every required layer file exists at the active master size (0 errors)."""
    errors = validate_sprites(cfg, palette, profile, SPRITES)
    assert errors == 0


def test_compose_sample_nft_is_master_rgba(cfg, palette, profile):
    """A real rolled trait set composites to a master-sized RGBA canvas."""
    engine = RollEngine(cfg)
    placements = derive_placements(TEST_SALT, cfg)
    manifest = engine.roll_chest(
        TEST_SALT, COIN_A, "castaway", 1, 1, placements, "prov-render-test",
    )
    entry = next(e for e in manifest["nfts"] if e["type"] == "generated")
    store = SpriteStore(cfg, palette, profile, SPRITES)
    img = compose(store, entry["traits"], entry.get("depth_zone"))
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"
    assert img.size == (profile.master_px, profile.master_px)
    # Non-empty composite (not a fully transparent blank).
    extrema = img.getextrema()
    alpha_max = extrema[3][1]
    assert alpha_max > 0


def test_background_layers_are_exempt_from_the_ink_grade(cfg, palette, profile):
    """A sky's authored hue must survive compositing.

    The global vertical ink grade is meant to unify *ink strokes*. Running the
    sky plate through it at strength 0.84 repainted every sky in the zone ramp
    (a moonlit navy came out hot magenta) and, because the grade gates on a
    hard alpha threshold, stamped a rectangular block edge where the wash
    crossed it. `palette.background_layers` names the exempt set; this asserts
    the exemption holds.
    """
    assert palette.background_layers == {"sky", "sea"}
    store = SpriteStore(cfg, palette, profile, SPRITES)
    traits = {
        "sky": "Moonlit", "sea": "Calm", "scene_element": "None",
        "ship_class": "Raft", "ship_condition": "Floating", "body": "Green",
        "pose": "Standing", "clothing": "Hoodie", "eyes": "Normal",
        "mouth": "None", "hat": "None", "aura": "None",
    }
    plate = store.get("sky", traits, "surface")
    assert plate is not None
    composed = compose(store, traits, zone="surface")

    import numpy as np

    # Sample the crown, where the sky is strongest and nothing else is drawn.
    src = np.asarray(plate.convert("RGBA"), dtype=np.int16)[:220, :, :]
    out = np.asarray(composed.convert("RGBA"), dtype=np.int16)[:220, :, :]
    strong = src[:, :, 3] > 150
    assert strong.any(), "fixture sky has no strong region to sample"
    # 'surface' grades toward crimson; an ungraded navy sky must stay cool.
    assert out[:, :, 2][strong].mean() > out[:, :, 0][strong].mean(), \
        "sky crown was repainted warm by the ink grade"


def test_resize_outputs_match_requested_size(cfg, palette, profile):
    engine = RollEngine(cfg)
    placements = derive_placements(TEST_SALT, cfg)
    manifest = engine.roll_chest(
        TEST_SALT, COIN_A, "castaway", 1, 1, placements, "prov-render-resize",
    )
    entry = next(e for e in manifest["nfts"] if e["type"] == "generated")
    store = SpriteStore(cfg, palette, profile, SPRITES)
    master = compose(store, entry["traits"], entry.get("depth_zone"))
    for size in profile.outputs[:2]:
        out = resize_to(master, size, profile, scale_mode="exact")
        assert out.size == (size, size)
        assert out.mode == "RGBA"
