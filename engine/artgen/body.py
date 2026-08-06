# SPDX-License-Identifier: MIT
"""Body layer: 8 colour variants x 6 poses, derived from the source plates.

The defect this fixes
---------------------
``sprites/body`` holds 48 filenames but only **12 unique images**. ``blue``,
``emerald``, ``green`` and ``zombie`` were byte-identical to one another, and
``chrome``, ``corrupted``, ``ghost`` and ``gold`` each repeated a single image
across all six poses. So "Blue Standing" and "Green Sitting" minted the *same
picture* — a fairness problem, not just an art one, because a buyer paying for a
rarer combination received a duplicate.

A second, quieter defect: the trait names did not match the art. ``blue_on_bow``
rendered a **red** character, because the four "colour variants" were the same
file rather than four colourways.

The fix
-------
Make the filename mean what it says: *pose* selects the composition, *variant*
selects the colourway.

``render("gold_sitting")`` takes the sitting pose plate and pushes it through
the gold gradient map — a luminance-indexed remap onto a master-palette ramp,
which preserves every line and every tonal relationship in the drawing while
restating its colour. This is how a colourway of an illustration is properly
made; it is not a hue rotation.

Every one of the twelve original images is kept in service: the five shared
pose plates supply five poses, and each variant with bespoke standing art keeps
that art as *its* standing source. Nothing is thrown away and all 48 outputs
differ.

Sources are read from ``vault/sprites-v1/body/`` — never from ``sprites/body/``
— so the derivation is idempotent and cannot compound on its own output.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from .core import load_palette, ramp_color

ROOT = Path(__file__).resolve().parent.parent.parent
VAULT_BODY = ROOT / "vault" / "sprites-v1" / "body"
CONFIG = ROOT / "config"

PAL = load_palette()

POSES = ("back_turned", "looking_down", "on_bow", "saluting", "sitting", "standing")

POSE_SOURCE = {
    "back_turned": "blue_back_turned",
    "looking_down": "blue_looking_down",
    "on_bow": "blue_on_bow",
    "saluting": "blue_saluting",
    "sitting": "blue_sitting",
}
"""Shared composition per pose. These five plates were identical across the
blue/emerald/green/zombie variants, so they are the collection's pose art."""

STANDING_SOURCE = {
    "blue": "blue_standing",
    "emerald": "emerald_standing",
    "green": "green_standing",
    "zombie": "green_standing",
    "chrome": "chrome_standing",
    "corrupted": "corrupted_standing",
    "ghost": "ghost_standing",
    "gold": "gold_standing",
}
"""Standing is where the bespoke art lives: chrome, corrupted, ghost and gold
each had one unique illustration, and this keeps each of them in service as
that variant's standing pose instead of discarding it."""


@dataclass(frozen=True)
class Colourway:
    """A luminance ramp, light end first, that restates the drawing's colour."""

    key: str
    stops: tuple[str, ...]
    notes: str = ""


COLOURWAYS: dict[str, Colourway] = {
    "green": Colourway(
        "green", ("pale_green", "bright_green", "chia_green", "deep_teal", "deep_ink"),
        "common — the natural, muted green"),
    "blue": Colourway(
        "blue", ("pale_blue", "steel_blue", "sea_blue", "navy", "ink_black")),
    "zombie": Colourway(
        "zombie", ("pale_green", "teal_green", "slate_gray", "deep_violet", "deep_ink"),
        "sickly: the midtones go grey before the shadows go violet"),
    "ghost": Colourway(
        "ghost", ("bone_white", "ash_gray", "pale_blue", "steel_blue", "deep_navy"),
        "epic — spectral and pale, but the shadow end still reaches a true dark: "
        "the composite ground is bone white, so a ramp that stops at grey makes "
        "the figure vanish into it"),
    "corrupted": Colourway(
        "corrupted", ("lavender", "amethyst", "violet", "deep_violet", "ink_black")),
    "gold": Colourway(
        "gold", ("sand", "pale_gold", "gold", "bronze", "deep_ink"),
        "legendary — treasure light"),
    "emerald": Colourway(
        "emerald", ("bone_white", "pale_green", "chia_green", "teal_green", "abyss_navy"),
        "legendary, Chia-coded — jewel contrast, brighter highlight and deeper "
        "shadow than the common green"),
    "chrome": Colourway(
        "chrome", ("bone_white", "ash_gray", "slate_gray", "shadow_navy", "ink_black"),
        "mythic — achromatic"),
}

VARIANTS = tuple(COLOURWAYS)


def all_keys() -> list[str]:
    """The 48 sprite stems, matching ``body/{variant}_{pose}.png``."""
    return [f"{v}_{p}" for v in VARIANTS for p in POSES]


def source_for(key: str) -> str:
    """Which vaulted plate supplies the drawing for this variant/pose."""
    variant, pose = split_key(key)
    if pose == "standing":
        return STANDING_SOURCE[variant]
    return POSE_SOURCE[pose]


def split_key(key: str) -> tuple[str, str]:
    for pose in POSES:
        if key.endswith("_" + pose):
            variant = key[: -len(pose) - 1]
            if variant in COLOURWAYS:
                return variant, pose
    raise KeyError(f"not a body sprite key: {key!r}")


@lru_cache(maxsize=16)
def _lut(variant: str) -> np.ndarray:
    """256-entry colour lookup indexed by luminance (0 = shadow, 255 = light)."""
    stops = [PAL[n] for n in COLOURWAYS[variant].stops]
    return np.asarray(
        [ramp_color(stops, 1.0 - i / 255.0) for i in range(256)], dtype=np.uint8
    )


def gradient_map(img: Image.Image, variant: str) -> Image.Image:
    """Restate an illustration's colour without touching its drawing.

    Luminance selects the output colour, so line weight, shading and every
    tonal relationship survive exactly; only the palette changes. Alpha is
    carried through untouched, which keeps the ink edges and the figure's
    silhouette identical to the source.
    """
    arr = np.asarray(img.convert("RGBA"))
    rgb = arr[:, :, :3].astype(np.float32)
    lum = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2])
    idx = np.clip(np.rint(lum), 0, 255).astype(np.uint8)
    out = np.dstack([_lut(variant)[idx], arr[:, :, 3]])
    out[out[:, :, 3] == 0] = 0
    return Image.fromarray(out, mode="RGBA")


@lru_cache(maxsize=16)
def _blanked_source(name: str, size: int) -> Image.Image:
    """A vaulted source plate with its drawn pupil removed.

    The ``eyes`` layer supplies the pupil, so the character's own one has to go
    or every composite shows two. Everything else the artist drew — iris,
    sclera, lid, socket — survives, which is the whole point of removing so
    little: that linework is what makes the plates good, and no procedural
    sprite can replace it.

    Cached because 48 body plates derive from only 12 sources.
    """
    from . import rig
    from .repair import blank_for

    src_path = VAULT_BODY / f"{name}.png"
    if not src_path.is_file():
        raise FileNotFoundError(
            f"{src_path} is missing — the body layer derives from the vault, "
            "never from sprites/body/"
        )
    img = Image.open(src_path).convert("RGBA")
    if img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS)
    return blank_for(name, img, rig.ANNOTATIONS[name])


def render(trait_key: str, size: int = 2048) -> Image.Image:
    """Derive one body plate. Deterministic; depends only on vaulted source art."""
    variant, _ = split_key(trait_key)
    return gradient_map(_blanked_source(source_for(trait_key), size), variant)


def expected_from_traits() -> set[str]:
    """The 48 keys traits.json implies, via body.sprite_pattern x pose."""
    doc = json.loads((CONFIG / "traits.json").read_text(encoding="utf-8"))
    body = next(ly for ly in doc["layers"] if ly["name"] == "body")
    pose = next(ly for ly in doc["layers"] if ly["name"] == "pose")

    def snake(name: str) -> str:
        import re

        s = name.lower().replace("'", "").replace("-", " ")
        s = re.sub(r"[^a-z0-9 ]", "", s)
        return re.sub(r" +", "_", s.strip())

    return {
        f"{snake(b['name'])}_{snake(p['name'])}"
        for b in body["traits"] for p in pose["traits"]
    }
