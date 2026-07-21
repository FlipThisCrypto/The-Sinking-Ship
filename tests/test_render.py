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
