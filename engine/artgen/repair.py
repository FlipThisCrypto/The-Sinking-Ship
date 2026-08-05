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


BLANK_OVERRIDES: dict[str, dict[str, float]] = {
    # One global threshold cannot serve twelve stylistically different
    # illustrations: at a single setting `corrupted` and `ghost` lost their
    # socket contour while `chrome` kept its whole eyeball. `cut_pct` is the
    # skin-variation percentile above which a pixel counts as "not skin"
    # (lower removes more), `cover` the guaranteed ellipse in eye widths.
    "chrome_standing": {"cut_pct": 62.0, "cover": 1.45},
    "corrupted_standing": {"cut_pct": 90.0, "cover": 0.80},
    "ghost_standing": {"cut_pct": 90.0, "cover": 0.85},
    "blue_standing": {"cut_pct": 86.0, "cover": 0.90},
    "blue_saluting": {"cut_pct": 74.0, "cover": 1.10},
}
"""Per-plate blanking parameters, tuned against the before/after proof sheet."""


def blank_eye_socket(img: Image.Image, eye_x: float, eye_y: float,
                     eye_w: float, *, cover: float = 0.98,
                     seed_from: float = 1.22,
                     cut_pct: float = 80.0) -> Image.Image:
    """Remove the drawn **eyeball**, leaving the socket and lid intact.

    Why only the eyeball: the eye sits inside a network of hand-drawn contour
    lines — lid, socket, skull edge — and diffusion inpainting cannot invent
    line art, so masking the whole eye smears those contours into mush (tried,
    with both Telea and Navier-Stokes, at several radii). Keeping the socket is
    also better art direction: the character's own linework goes on framing the
    eye, and the ``eyes`` trait supplies only what sits inside it.

    The fill follows *local* colour rather than an average. A single median
    skin tone taken from a ring around the eye picks up whatever shading
    happens to fall in that ring — on ``blue_looking_down`` it produced a red
    disc on a pale face. Instead every removed pixel takes the colour of its
    nearest surviving skin pixel, and the result is blurred, so the fill
    inherits the face's local gradient.

    Alpha is untouched: the eye is interior to the figure, so its silhouette
    does not change.
    """
    arr = np.asarray(img.convert("RGBA")).astype(np.float32)
    rgb, alpha = arr[:, :, :3], arr[:, :, 3]
    h, w = alpha.shape
    r = max(2.0, eye_w * w * 0.5)
    cx, cy = eye_x * w, eye_y * h

    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot((xs - cx) / r, (ys - cy) / (r * 0.95))

    # The eyeball's true extent is found, not assumed. A hand-measured eye
    # width is good enough to *aim* at the eye but not to bound it — on
    # `chrome` and `ghost` an assumed radius left half the eyeball behind.
    # Grow the region of not-skin pixels connected to the anchor, capped at a
    # radius so it cannot leak out along the hair.
    near = d < 3.0
    skin_ref = (alpha > 200) & (d > seed_from) & (d < seed_from * 3.0)
    if skin_ref.sum() < 100:
        return img
    skin = np.median(rgb[skin_ref], axis=0)
    diff = np.linalg.norm(rgb - skin.reshape(1, 1, 3), axis=2)
    # Loose enough to include a mid-tone iris: at p92 only the pupil and the
    # lid line cleared the bar and the iris survived as a ring. Per-plate
    # overrides live in BLANK_OVERRIDES.
    cut = max(18.0, float(np.percentile(diff[skin_ref], cut_pct)))
    seed = ((diff > cut) & near & (alpha > 120)).astype(np.uint8)
    seed = cv2.morphologyEx(
        seed, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    n, labels = cv2.connectedComponents(seed, 8)
    lab = labels[int(round(cy)), int(round(cx))]
    if lab == 0:                      # anchor landed on skin — take the nearest blob
        cand = [i for i in range(1, n) if (labels == i).sum() > 40]
        if not cand:
            return img
        lab = min(cand, key=lambda i: float(
            np.hypot(*(np.array(np.nonzero(labels == i)).mean(axis=1)
                       - np.array([cy, cx])))))
    eyeball = labels == lab
    eyeball = cv2.dilate(
        eyeball.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                  (max(3, int(r * 0.18)) | 1,) * 2)).astype(bool)

    # Union with the measured ellipse: detection bounds the eyeball better than
    # a hand measurement can, but the measurement guarantees a floor.
    removed = (eyeball | (d < cover)) & (d < 3.0)
    if not removed.any():
        return img

    grown = cv2.dilate(removed.astype(np.uint8),
                       cv2.getStructuringElement(
                           cv2.MORPH_ELLIPSE, (max(3, int(r * 0.5)) | 1,) * 2)).astype(bool)
    donor = (alpha > 200) & (~grown) & (diff < cut)

    # Nearest surviving donor for every removed pixel.
    _, labels = cv2.distanceTransformWithLabels(
        (~donor).astype(np.uint8), cv2.DIST_L2, 3,
        labelType=cv2.DIST_LABEL_PIXEL)
    dy, dx = np.nonzero(donor)
    order = labels[donor]
    lookup = np.zeros(int(labels.max()) + 1, dtype=np.int64)
    lookup[order] = dy * w + dx
    flat = lookup[labels]
    filled = rgb.reshape(-1, 3)[flat.ravel()].reshape(h, w, 3)

    filled = cv2.GaussianBlur(filled, (0, 0), max(1.0, r * 0.40))
    feather = cv2.GaussianBlur(removed.astype(np.float32), (0, 0),
                               max(1.0, r * 0.10))[:, :, None]
    feather = np.clip(feather * 1.35, 0.0, 1.0)
    out = rgb * (1.0 - feather) + filled * feather
    out = np.clip(np.rint(np.dstack([out, alpha])), 0, 255).astype(np.uint8)
    out[out[:, :, 3] == 0] = 0
    return Image.fromarray(out, mode="RGBA")


def blank_for(name: str, img: Image.Image, anchor) -> Image.Image:
    """Blank one source plate using its tuned parameters."""
    kw = dict(BLANK_OVERRIDES.get(name, {}))
    return blank_eye_socket(img, anchor.eye_x, anchor.eye_y, anchor.eye_w, **kw)
