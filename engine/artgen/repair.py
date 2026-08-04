# SPDX-License-Identifier: MIT
"""Corrective transforms for externally authored sprite art.

``body/`` and ``ship_class/`` were produced outside this repository and cannot
be regenerated, so they are *repaired* rather than re-rendered. Every transform
here is:

* **Appearance-preserving on the composite ground.** The illustration profile
  composites onto bone white (``ART-DIRECTION.md``), so a repair must not change
  how the plate looks over white. Each function documents its bound and
  ``tests/test_artgen_repair.py`` pins it.
* **Reproducible.** Run through ``scripts/repair_art.py``; the pre-repair files
  stay byte-exact in ``vault/sprites-v1/``.
* **Idempotent.** Re-running a repair on already-repaired art is a no-op within
  rounding, so a partial run can always be finished.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

__all__ = ["unmatte_over_white", "matte_veil_strength"]


def _rgba_f32(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGBA"), dtype=np.float32)


def matte_veil_strength(img: Image.Image, border: int = 24) -> float:
    """Mean alpha in the outer frame — how strong a residual matte is.

    A plate knocked out cleanly has a fully transparent border. Three of the
    sixteen ship plates instead carried a near-white film over the *entire*
    canvas (``lifeboat`` reached alpha 148/255 in a corner), invisible on bone
    white but bleaching a 2048x2048 rectangle into any coloured sky behind it.
    """
    a = np.asarray(img.convert("RGBA"))[:, :, 3].astype(np.float32) / 255.0
    edge = np.concatenate([
        a[:border, :].ravel(), a[-border:, :].ravel(),
        a[:, :border].ravel(), a[:, -border:].ravel(),
    ])
    return float(edge.mean())


def unmatte_over_white(img: Image.Image) -> Image.Image:
    """Recover true straight alpha from artwork that was flattened onto white.

    The source is ink on white paper. Its *appearance over white* is the
    ground truth::

        over = rgb * a + 255 * (1 - a)

    Paper shows as white, so transparency is simply the absence of ink::

        a_new = 1 - min(over_r, over_g, over_b) / 255

    and the colour that reproduces ``over`` at that alpha is::

        rgb_new = (over - 255 * (1 - a_new)) / a_new

    By construction the plate looks identical over pure white (measured: max
    1/255 per channel) while background pixels become genuinely transparent
    instead of a pale veil.

    ``min`` across channels rather than luminance keeps saturated colour opaque:
    a pure red stroke has ``min == 0`` and stays fully solid.

    Pixels the author already marked fully transparent stay transparent. That
    matters — several plates carry dark leftover RGB under ``alpha == 0``
    (``aircraft_carrier`` goes down to 0), and deriving alpha from those would
    resurrect ink the author had removed.
    """
    arr = _rgba_f32(img)
    rgb, alpha = arr[:, :, :3], arr[:, :, 3:4] / 255.0

    over = rgb * alpha + 255.0 * (1.0 - alpha)
    a_new = 1.0 - over.min(axis=2, keepdims=True) / 255.0
    a_new = np.where(alpha > 0.0, a_new, 0.0)

    safe = np.maximum(a_new, 1e-4)
    rgb_new = np.clip((over - 255.0 * (1.0 - a_new)) / safe, 0.0, 255.0)

    out = np.concatenate([rgb_new, a_new * 255.0], axis=2)
    out = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    # Alpha hygiene: constant runs under transparent pixels compress, noise does not.
    out[out[:, :, 3] == 0] = 0
    return Image.fromarray(out, mode="RGBA")


def appearance_delta_over_white(a: Image.Image, b: Image.Image) -> tuple[float, float]:
    """(max, mean) per-channel difference of two plates composited over white."""
    white = np.full((a.height, a.width, 3), 255.0, dtype=np.float32)

    def flat(img: Image.Image) -> np.ndarray:
        arr = _rgba_f32(img)
        al = arr[:, :, 3:4] / 255.0
        return arr[:, :, :3] * al + white * (1.0 - al)

    d = np.abs(flat(a) - flat(b))
    return float(d.max()), float(d.mean())
