# SPDX-License-Identifier: MIT
"""Canvas, noise, colour ramps and disciplined PNG output for artgen.

Design notes
------------
*Straight (non-premultiplied) alpha* is used throughout because the sprite
contract is RGBA PNG and the compositor (``engine/render_engine.py``) uses
``Image.alpha_composite``. ``Canvas.over`` performs the standard source-over
blend in float32 and keeps colour meaningful in low-alpha regions.

*Determinism* is a hard requirement: 44,444 mints are rendered from these
sprites and the fairness pipeline hashes the results. Every random draw comes
from a ``numpy.random.Generator`` seeded by ``seed_for(key)`` — a SHA-256 of
the sprite key — never from global RNG state or wall-clock time.

*Alpha hygiene* matters for repository size as much as for correctness: the
pre-round sprites carried noisy RGB underneath ``alpha == 0`` pixels, which
defeats PNG's filters. ``save_sprite`` zeroes fully-transparent pixels before
encoding, which typically shrinks a 2048x2048 plate by an order of magnitude.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np
from PIL import Image

RGB = tuple[int, int, int]
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

MASTER_REF_PX = 2048
"""Resolution every hand-tuned length in a layer renderer is expressed in.

Stroke widths, blur radii and sprite-scale detail are authored against this
number and converted with :func:`master_scale`. Without that conversion a
preview render is a different *drawing*, not a smaller one: a 3 px ray is
legible at 2048 and gone at 512, so what you tune at preview size is not what
ships. See :func:`master_scale`.
"""


def master_scale(size: int) -> float:
    """Factor converting a master-reference length to ``size`` canvas pixels."""
    return float(size) / MASTER_REF_PX


# ------------------------------------------------------------------ palette


def hex_to_rgb(value: str) -> RGB:
    v = value.lstrip("#")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


def load_palette(path: Path | None = None) -> dict[str, RGB]:
    """Master palette as ``{name: (r, g, b)}`` from config/palette.json."""
    doc = json.loads((path or CONFIG_DIR / "palette.json").read_text(encoding="utf-8"))
    return {c["name"]: hex_to_rgb(c["hex"]) for c in doc["master"]}


# ------------------------------------------------------------------ seeding


def seed_for(key: str) -> int:
    """Stable 63-bit seed from a sprite key (e.g. ``"sky/aurora"``)."""
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big") >> 1


def rng_for(key: str) -> np.random.Generator:
    return np.random.default_rng(seed_for(key))


# ------------------------------------------------------------------- ramps


def ramp_color(stops: Sequence[Sequence[float]], t: float) -> RGB:
    """Sample a multi-stop ramp at ``t`` in [0, 1] (top -> bottom)."""
    t = float(np.clip(t, 0.0, 1.0))
    if len(stops) == 1:
        return tuple(int(round(c)) for c in stops[0])  # type: ignore[return-value]
    segs = len(stops) - 1
    x = t * segs
    i = min(int(x), segs - 1)
    f = x - i
    a, b = np.asarray(stops[i], dtype=np.float32), np.asarray(stops[i + 1], dtype=np.float32)
    return tuple(int(round(v)) for v in (a + (b - a) * f))  # type: ignore[return-value]


def ramp_image(stops: Sequence[Sequence[float]], h: int, w: int,
               t0: float = 0.0, t1: float = 1.0) -> np.ndarray:
    """(h, w, 3) float32 image of a vertical ramp spanning rows ``t0``..``t1``.

    Rows outside the span clamp to the nearest stop, so a ramp can be aimed at
    a band (e.g. only the sky third) without a hard seam.
    """
    ts = np.linspace(0.0, 1.0, h, dtype=np.float32)
    span = max(1e-6, t1 - t0)
    ts = np.clip((ts - t0) / span, 0.0, 1.0)
    idx = ts * (len(stops) - 1)
    lo = np.floor(idx).astype(np.int32)
    lo = np.clip(lo, 0, len(stops) - 2) if len(stops) > 1 else np.zeros_like(lo)
    frac = (idx - lo).astype(np.float32)[:, None]
    arr = np.asarray(stops, dtype=np.float32)
    col = arr[lo] * (1.0 - frac) + arr[np.clip(lo + 1, 0, len(stops) - 1)] * frac
    return np.repeat(col[:, None, :], w, axis=1)


def smoothstep(edge0: np.ndarray | float, edge1: np.ndarray | float,
               x: np.ndarray | float) -> np.ndarray:
    """Hermite smoothstep; ``edge0 == edge1`` degenerates to a hard step.

    ``edge0`` may exceed ``edge1``, which gives a falling ramp — several
    envelopes rely on that. Edges may also be arrays, so a boundary can vary
    across the canvas (e.g. a per-column ragged hem).
    """
    e0 = np.asarray(edge0, dtype=np.float32)
    e1 = np.asarray(edge1, dtype=np.float32)
    span = e1 - e0
    degenerate = span == 0
    safe = np.where(degenerate, 1.0, span)
    t = np.clip((np.asarray(x, dtype=np.float32) - e0) / safe, 0.0, 1.0)
    out = t * t * (3.0 - 2.0 * t)
    if degenerate.any():
        out = np.where(degenerate, np.where(np.asarray(x) < e0, 0.0, 1.0), out)
    return np.asarray(out, dtype=np.float32)


# ------------------------------------------------------------------- noise


def value_noise(h: int, w: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth value noise in [0, 1], ``cells`` lattice points across the width.

    Built by bicubic-resampling a small random lattice — cheap, seedable and
    free of the directional artefacts a naive bilinear upsample produces.
    """
    cells = max(2, int(cells))
    ch = max(2, int(round(cells * h / max(1, w))))
    lattice = rng.random((ch + 3, cells + 3), dtype=np.float32)
    big = cv2.resize(lattice, (w + 3, h + 3), interpolation=cv2.INTER_CUBIC)
    out = big[1:h + 1, 1:w + 1]
    lo, hi = float(out.min()), float(out.max())
    return ((out - lo) / max(1e-6, hi - lo)).astype(np.float32)


def fbm(h: int, w: int, rng: np.random.Generator, octaves: int = 5,
        cells: int = 4, gain: float = 0.5, lacunarity: float = 2.0) -> np.ndarray:
    """Fractal Brownian motion in [0, 1] — the base texture for cloud and wash."""
    total = np.zeros((h, w), dtype=np.float32)
    amp, freq, norm = 1.0, float(cells), 0.0
    for _ in range(max(1, octaves)):
        total += amp * value_noise(h, w, int(round(freq)), rng)
        norm += amp
        amp *= gain
        freq *= lacunarity
    total /= max(1e-6, norm)
    lo, hi = float(total.min()), float(total.max())
    return ((total - lo) / max(1e-6, hi - lo)).astype(np.float32)


def domain_warp(field: np.ndarray, rng: np.random.Generator, amount: float = 40.0,
                cells: int = 3) -> np.ndarray:
    """Advect ``field`` along a smooth random vector field.

    This is what turns bland noise into the drifting, brush-dragged forms the
    reference art uses for cloud, smoke and water.
    """
    h, w = field.shape[:2]
    dx = (value_noise(h, w, cells, rng) - 0.5) * 2.0 * amount
    dy = (value_noise(h, w, cells, rng) - 0.5) * 2.0 * amount
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    map_x = np.clip(xs + dx, 0, w - 1).astype(np.float32)
    map_y = np.clip(ys + dy, 0, h - 1).astype(np.float32)
    return cv2.remap(field, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REFLECT)


def blur(field: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur that tolerates sigma <= 0 (returns the input unchanged)."""
    if sigma <= 0:
        return field
    k = int(sigma * 4) | 1
    return cv2.GaussianBlur(field, (k, k), sigma, borderType=cv2.BORDER_REFLECT)


# ------------------------------------------------------------------ canvas


class Canvas:
    """Float32 straight-alpha RGBA accumulation buffer.

    ``rgb`` is 0..255 float, ``alpha`` is 0..1 float. Compositing is
    source-over; colour is un-mixed on write so partially transparent regions
    keep a sensible hue instead of drifting toward black.
    """

    __slots__ = ("h", "w", "rgb", "alpha")

    def __init__(self, size: int = 2048, h: int | None = None, w: int | None = None):
        self.h = int(h if h is not None else size)
        self.w = int(w if w is not None else size)
        self.rgb = np.zeros((self.h, self.w, 3), dtype=np.float32)
        self.alpha = np.zeros((self.h, self.w), dtype=np.float32)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.h, self.w)

    def over(self, rgb: np.ndarray, alpha: np.ndarray) -> "Canvas":
        """Source-over composite of a full-canvas layer.

        ``rgb`` may be (h, w, 3) or a broadcastable colour; ``alpha`` is
        (h, w) in 0..1.
        """
        src_a = np.clip(np.asarray(alpha, dtype=np.float32), 0.0, 1.0)
        src_rgb = np.broadcast_to(np.asarray(rgb, dtype=np.float32),
                                  (self.h, self.w, 3))
        out_a = src_a + self.alpha * (1.0 - src_a)
        safe = np.maximum(out_a, 1e-6)[:, :, None]
        num = (src_rgb * src_a[:, :, None]
               + self.rgb * (self.alpha * (1.0 - src_a))[:, :, None])
        self.rgb = np.where(out_a[:, :, None] > 1e-6, num / safe, self.rgb)
        self.alpha = out_a
        return self

    def over_color(self, color: Sequence[float], alpha: np.ndarray) -> "Canvas":
        c = np.asarray(color, dtype=np.float32).reshape(1, 1, 3)
        return self.over(np.broadcast_to(c, (self.h, self.w, 3)), alpha)

    def multiply_alpha(self, factor: np.ndarray | float) -> "Canvas":
        self.alpha = np.clip(self.alpha * np.asarray(factor, dtype=np.float32), 0.0, 1.0)
        return self

    def to_image(self) -> Image.Image:
        """Bake to an 8-bit RGBA ``PIL.Image`` with transparent pixels zeroed."""
        rgb = np.clip(np.rint(self.rgb), 0, 255).astype(np.uint8)
        a = np.clip(np.rint(self.alpha * 255.0), 0, 255).astype(np.uint8)
        rgb[a == 0] = 0
        return Image.fromarray(np.dstack([rgb, a]), mode="RGBA")

    def copy(self) -> "Canvas":
        c = Canvas(h=self.h, w=self.w)
        c.rgb = self.rgb.copy()
        c.alpha = self.alpha.copy()
        return c


# --------------------------------------------------------------------- io


def save_sprite(img: Image.Image | Canvas, path: Path, *, size: int = 2048) -> int:
    """Write a sprite PNG with alpha hygiene and maximum lossless compression.

    Returns the file size in bytes. Fully-transparent pixels get RGB zeroed
    (they are invisible either way, and constant runs compress) before
    encoding with ``optimize=True``.
    """
    if isinstance(img, Canvas):
        img = img.to_image()
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    if img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS)
    arr = np.array(img)
    arr[arr[:, :, 3] == 0] = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, mode="RGBA").save(path, format="PNG", optimize=True)
    return path.stat().st_size


def alpha_stats(img: Image.Image) -> dict[str, float]:
    """Coverage diagnostics used by the layer QA tests."""
    a = np.asarray(img.convert("RGBA"), dtype=np.float32)[:, :, 3] / 255.0
    return {
        "mean": float(a.mean()),
        "max": float(a.max()),
        "coverage": float((a > 0.02).mean()),
        "opaque": float((a > 0.98).mean()),
    }


def unique_colors(img: Image.Image, min_alpha: int = 24) -> int:
    """Distinct RGB values among reasonably visible pixels."""
    arr = np.asarray(img.convert("RGBA"))
    vis = arr[arr[:, :, 3] >= min_alpha][:, :3]
    if vis.size == 0:
        return 0
    packed = (vis[:, 0].astype(np.uint32) << 16
              | vis[:, 1].astype(np.uint32) << 8
              | vis[:, 2].astype(np.uint32))
    return int(np.unique(packed).size)


def iter_layer_pngs(root: Path, layer: str) -> Iterable[Path]:
    return sorted((root / layer).glob("*.png"))
