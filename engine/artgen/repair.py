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

import cv2
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


# --------------------------------------------------------- blanking the face


BLANK_OVERRIDES: dict[str, dict[str, float]] = {}
"""Per-plate blanking parameters, tuned against the before/after proof sheet.

One global threshold cannot serve twelve stylistically different illustrations.
"""


def blank_pupil(img: Image.Image, eye_x: float, eye_y: float, eye_w: float, *,
                feature_frac: float = 0.34, cover: float = 1.0,
                seed_from: float = 1.55, cut_pct: float = 55.0,
                smooth: float = 0.45) -> Image.Image:
    """Remove the drawn **pupil**, leaving iris, sclera, lid and socket intact.

    The character keeps its own eye — its iris colour, its lid weight, its
    socket linework, all hand-drawn — and the ``eyes`` trait supplies only the
    pupil and, where a trait needs it, a lid drawn over the top. That is the
    part that actually varies between traits, and it is the smallest edit that
    makes the layer work.

    Removing more was tried and rejected. Masking the whole eye and inpainting
    (Telea and Navier-Stokes, several radii) smears: the eye sits inside a
    network of hand-drawn contour lines and diffusion cannot invent line art.
    Removing the whole eyeball loses the iris, which is some of the best
    drawing in the plates.

    The fill takes colour from the **iris ring immediately around the pupil**,
    by nearest surviving donor, then blurs. Sampling a wider ring picks up the
    lid and smears dark into the fill; sampling a flat median picks up whatever
    shading happens to fall in the ring.

    Alpha is never touched: the pupil is interior to the figure, so the
    silhouette and compositing behaviour cannot change.

    ``feature_frac``
        pupil radius as a fraction of eye width — what to remove.
    ``seed_from``
        donor ring start, in pupil radii. Must clear the pupil but stay inside
        the iris.
    ``cut_pct``
        percentile of local colour variation above which a pixel counts as
        "not iris". Lower removes more.
    """
    arr = np.asarray(img.convert("RGBA")).astype(np.float32)
    rgb, alpha = arr[:, :, :3], arr[:, :, 3]
    h, w = alpha.shape
    r = max(2.0, eye_w * w * feature_frac)
    cx, cy = eye_x * w, eye_y * h

    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot((xs - cx) / r, (ys - cy) / r)

    ring = (d > seed_from) & (d < seed_from * 2.0) & (alpha > 200)
    if ring.sum() < 60:
        return img
    iris = np.median(rgb[ring], axis=0)
    diff = np.linalg.norm(rgb - iris.reshape(1, 1, 3), axis=2)
    cut = max(14.0, float(np.percentile(diff[ring], cut_pct)))

    seed = ((diff > cut) & (d < seed_from) & (alpha > 120)).astype(np.uint8)
    seed = cv2.morphologyEx(
        seed, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    n, labels = cv2.connectedComponents(seed, 8)
    lab = labels[int(round(cy)), int(round(cx))]
    blob = (labels == lab) if lab else np.zeros_like(seed, bool)

    removed = (blob | (d < cover)) & (d < seed_from)
    if not removed.any():
        return img

    grown = cv2.dilate(removed.astype(np.uint8),
                       cv2.getStructuringElement(
                           cv2.MORPH_ELLIPSE, (max(3, int(r * 0.6)) | 1,) * 2)).astype(bool)
    donor = (alpha > 200) & (~grown) & (d < seed_from * 2.4)
    if donor.sum() < 40:
        return img

    _, lbl = cv2.distanceTransformWithLabels(
        (~donor).astype(np.uint8), cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL)
    dy, dx = np.nonzero(donor)
    lookup = np.zeros(int(lbl.max()) + 1, dtype=np.int64)
    lookup[lbl[donor]] = dy * w + dx
    filled = rgb.reshape(-1, 3)[lookup[lbl].ravel()].reshape(h, w, 3)
    filled = cv2.GaussianBlur(filled, (0, 0), max(1.0, r * smooth))

    feather = cv2.GaussianBlur(removed.astype(np.float32), (0, 0),
                               max(1.0, r * 0.16))[:, :, None]
    feather = np.clip(feather * 1.30, 0.0, 1.0)
    out = rgb * (1.0 - feather) + filled * feather
    out = np.clip(np.rint(np.dstack([out, alpha])), 0, 255).astype(np.uint8)
    out[out[:, :, 3] == 0] = 0
    return Image.fromarray(out, mode="RGBA")


def blank_for(name: str, img: Image.Image, anchor) -> Image.Image:
    """Blank one source plate's pupil using its tuned parameters."""
    return blank_pupil(img, anchor.eye_x, anchor.eye_y, anchor.eye_w,
                       **dict(BLANK_OVERRIDES.get(name, {})))
