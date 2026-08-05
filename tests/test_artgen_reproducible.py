# SPDX-License-Identifier: MIT
"""Every committed plate must regenerate byte-identically from its renderer.

This is the guard for the promise the art pipeline makes: *regenerating a layer
produces no git churn unless the renderer actually changed*. Without it the
sprites on disk quietly drift away from the code that claims to produce them,
and nobody finds out until a regeneration produces a diff nobody can explain.

It has already caught one real drift: a numerical change to ``smoothstep`` that
downcast its edge arithmetic from float64 to float32 shifted nine pixels per
sky plate by one 8-bit level. The sea layer was regenerated afterwards, the sky
layer was not, so the two layers were built by different code.

Full-resolution and therefore slow (~3 min across the generated layers). Deselect with
``-m "not slow"`` when iterating on something unrelated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from artgen import (  # noqa: E402
    aura,
    body,
    scene_element,
    sea,
    ship_condition,
    sky,
)

LAYERS = {"sky": sky, "sea": sea, "scene_element": scene_element,
          "ship_condition": ship_condition, "aura": aura, "body": body}


def _cases() -> list[tuple[str, str]]:
    return [(layer, key) for layer, mod in LAYERS.items() for key in mod.all_keys()]


@pytest.mark.slow
@pytest.mark.parametrize("layer,key", _cases())
def test_committed_plate_matches_its_renderer(layer: str, key: str):
    path = ROOT / "sprites" / layer / f"{key}.png"
    assert path.is_file(), f"{layer}/{key}.png is missing"
    committed = np.asarray(Image.open(path).convert("RGBA"))
    result = LAYERS[layer].render(key, size=2048)
    fresh = np.asarray(result.to_image() if hasattr(result, "to_image") else result)
    if np.array_equal(fresh, committed):
        return
    differing = int((np.abs(fresh.astype(int) - committed.astype(int)).max(axis=2) > 0).sum())
    worst = int(np.abs(fresh.astype(int) - committed.astype(int)).max())
    pytest.fail(
        f"sprites/{layer}/{key}.png is stale: {differing} pixels differ "
        f"(max {worst}/255). Re-run: python scripts/gen_art.py --layer {layer}"
    )


def test_every_renderer_layer_is_registered_in_gen_art():
    """A renderer nobody can invoke cannot be regenerated, so it will drift."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gen_art", ROOT / "scripts" / "gen_art.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(LAYERS) <= set(mod.RENDERERS)
