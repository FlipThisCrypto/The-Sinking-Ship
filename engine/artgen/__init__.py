# SPDX-License-Identifier: MIT
"""artgen — the illustration art engine for THE SINKING SHIP.

Authors the production sprite layers in the Amano ink idiom described by
``docs/art-reference/ART-DIRECTION.md``: flowing calligraphic linework carrying
a vertical colour ramp (warm top -> deep navy/ink bottom) over a bone-white
ground, with selective washes rather than flat colour blocks.

The engine is a thin, dependency-light stack over numpy + OpenCV:

``core``
    ``Canvas`` (premultiplied-safe float RGBA compositing), value-noise / fBm,
    domain warping, vertical ramps, soft masks, blur, alpha hygiene and the
    size-disciplined PNG writer.
``ink``
    Stroke vocabulary: tapered calligraphic polylines, curl flourishes, wave
    ribbons, filigree, star fields and glow.

Two properties every layer renderer must hold:

**Deterministic.** Output depends only on the sprite key, so regenerating a
layer twice produces byte-identical PNGs and the git history stays meaningful.

**Resolution-independent.** Every hand-tuned length — stroke width, blur
radius, star size — is authored in *master-reference pixels* (see
``core.MASTER_REF_PX``) and converted with the render context's ``px()``
helper. Without that, a small render is a different drawing rather than a
smaller one, previews cannot be trusted, and every visual check costs a
full-resolution render.
"""
from __future__ import annotations

__version__ = "1.0.0"

MASTER_PX = 2048
"""Native authoring resolution (config/render.json illustration profile)."""

HORIZON = 0.58
"""Waterline as a fraction of canvas height — shared by sky, sea and ships."""

BONE_WHITE = (244, 244, 240)
"""The composite ground. Layers stay transparent; this is what shows through."""

from .core import (  # noqa: E402
    MASTER_REF_PX,
    Canvas,
    domain_warp,
    fbm,
    hex_to_rgb,
    load_palette,
    master_scale,
    ramp_color,
    ramp_image,
    save_sprite,
    seed_for,
    smoothstep,
    value_noise,
)
from .ink import (  # noqa: E402
    calligraphic_stroke,
    curl_flourish,
    glow,
    star_field,
    wave_ribbon,
)

__all__ = [
    "MASTER_PX",
    "MASTER_REF_PX",
    "HORIZON",
    "BONE_WHITE",
    "Canvas",
    "master_scale",
    "calligraphic_stroke",
    "curl_flourish",
    "domain_warp",
    "fbm",
    "glow",
    "hex_to_rgb",
    "load_palette",
    "ramp_color",
    "ramp_image",
    "save_sprite",
    "seed_for",
    "smoothstep",
    "star_field",
    "value_noise",
    "wave_ribbon",
]
