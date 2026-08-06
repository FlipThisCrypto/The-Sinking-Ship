# SPDX-License-Identifier: MIT
"""Body rig: where the head sits on each body plate, and how to land face art on it.

Why
---
``eyes``, ``mouth`` and ``hat`` are single sprites per trait — ``traits.json``
gives them no pose dimension — so one ``eyes/normal.png`` must land correctly on
all 48 body plates. Measured, the head moves a long way between them: eye
centres span x 0.26 to x 0.83 and head heights vary about 2.4x. The plates
cannot be normalised onto a shared rig without destroying their composition
(``blue_standing`` and ``emerald_standing`` are different pictures, not
recolours), so instead the *face layers* are transformed per body at composite
time. This module holds the map and the arithmetic.

How the numbers were obtained
-----------------------------
By hand, from the art, verified against a proof sheet — not by a detector.
Two automatic approaches were tried and discarded:

* a silhouette/shoulder-flare heuristic, whose confidence score turned out to
  be *inversely* correlated with correctness (the hair is wider than the skull,
  so it fired at the top of the hair) and which locked onto a smoke plume on
  ``blue_standing``;
* an OpenCV blob detector for the pupil, which fired on only 5 of the 12 unique
  images and picked the cigarette on ``blue_sitting``.

With twelve unique images, annotating them and *proving* the annotation is more
honest and more accurate than either. ``scripts/build_rig.py --sheet`` draws the
recorded anchor on every plate; a wrong entry is obvious at a glance.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = ROOT / "config"
RIG_PATH = CONFIG / "rig.json"

FACE_LAYERS = {"eyes": "eye_w", "mouth": "eye_w", "hat": "head_h"}
"""Face layer -> which anchor measure scales it.

Eyes and mouth are *features*, so they scale with feature size (``eye_w``).
A hat sits on the skull, so it scales with ``head_h``. Using one measure for
both gets one of them wrong: eye-to-head ratio varies by more than 2x here.
``clothing`` is absent because it keys off the torso, not the head.
"""


@dataclass(frozen=True)
class Anchor:
    """Head geometry for one plate, in normalised plate coordinates.

    ``eye_x``/``eye_y`` is the centre of the **dominant** eye: the single
    visible eye on a profile head, the nearer and larger one where two are
    drawn. Not the centre of the eye mass — the eyes layer draws one eye (the
    species cue is *a single large expressive eye*), so anchoring on the
    midpoint of a two-eyed face lands it on the bridge of the nose.

    ``eye_w`` is that eye's drawn width, outer lid to outer lid. It is what the
    eyes layer scales by, because eye-to-head ratio is *not* constant across
    these plates — ``gold`` has a small eye (0.042) on a normal head while
    ``blue_back_turned`` has a large one (0.090). Scaling eye art by head
    height therefore gets the size wrong on most of them.

    ``head_h`` is crown-to-chin, excluding hair. Hats scale by this instead,
    since a hat sits on the skull rather than on the features.

    Width, not height, is the scale reference: a half-lidded eye
    (``blue_sitting``) has a much reduced opening but an unchanged width.
    """

    eye_x: float
    eye_y: float
    head_h: float
    eye_w: float = 0.062
    facing: str = "right"


CANONICAL = Anchor(eye_x=0.520, eye_y=0.145, head_h=0.190, eye_w=0.062,
                   facing="right")
"""The rig face sprites are authored against.

Every value sits mid-distribution so no plate needs an extreme transform:
measured eye widths run 0.037-0.090, so scaling against 0.062 keeps every
factor inside 0.6x-1.5x.
"""

ANNOTATIONS: dict[str, Anchor] = {
    #                       eye_x  eye_y  head_h  eye_w
    "blue_back_turned":   Anchor(0.500, 0.163, 0.170, 0.090),
    "blue_looking_down":  Anchor(0.507, 0.240, 0.190, 0.075),
    "blue_on_bow":        Anchor(0.472, 0.162, 0.130, 0.075),
    "blue_saluting":      Anchor(0.537, 0.250, 0.180, 0.065),
    "blue_sitting":       Anchor(0.565, 0.210, 0.180, 0.045),
    "blue_standing":      Anchor(0.832, 0.424, 0.180, 0.065),
    "chrome_standing":    Anchor(0.555, 0.240, 0.330, 0.100, facing="left"),
    "corrupted_standing": Anchor(0.655, 0.265, 0.200, 0.050),
    "emerald_standing":   Anchor(0.448, 0.288, 0.170, 0.065),
    "ghost_standing":     Anchor(0.580, 0.195, 0.190, 0.090),
    "gold_standing":      Anchor(0.651, 0.262, 0.200, 0.042),
    "green_standing":     Anchor(0.653, 0.262, 0.190, 0.037),
}
"""Hand-annotated head anchors for the twelve unique source images.

Keyed by *source* plate; the 48 body sprites inherit whichever source supplies
their drawing (see ``artgen.body.source_for``).
"""


def plate_anchors() -> dict[str, Anchor]:
    """Anchor for every one of the 48 body sprite stems."""
    from . import body

    return {key: ANNOTATIONS[body.source_for(key)] for key in body.all_keys()}


# -------------------------------------------------------------- the transform


def face_transform(anchor: Anchor, canonical: Anchor = CANONICAL,
                   scale_by: str = "eye_w") -> tuple[float, float, float, bool]:
    """``(scale, dx, dy, mirror)`` taking face-sprite space onto this body.

    A point ``p`` authored against ``canonical`` lands at
    ``(p - canonical_eye) * scale + anchor_eye``, all in normalised
    coordinates. ``mirror`` is set when the body faces the other way, so a
    profile eye stays on the correct side of the skull.

    ``scale_by`` selects the measure: ``eye_w`` for features, ``head_h`` for
    hats. See ``FACE_LAYERS``.
    """
    scale = getattr(anchor, scale_by) / getattr(canonical, scale_by)
    mirror = anchor.facing != canonical.facing
    cx = 1.0 - canonical.eye_x if mirror else canonical.eye_x
    dx = anchor.eye_x - cx * scale
    dy = anchor.eye_y - canonical.eye_y * scale
    return scale, dx, dy, mirror


def apply_face_transform(sprite, anchor: Anchor, size: int,
                         canonical: Anchor = CANONICAL,
                         scale_by: str = "eye_w"):
    """Place a face sprite onto a body's head. Returns a full-canvas RGBA image."""
    from PIL import Image

    scale, dx, dy, mirror = face_transform(anchor, canonical, scale_by)
    if mirror:
        sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)
    new = max(1, round(size * scale))
    scaled = sprite.resize((new, new), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(scaled, (round(dx * size), round(dy * size)))
    return out


# ------------------------------------------------------------------- config


def build_doc() -> dict:
    return {
        "$comment": (
            "Head anchors per body plate, in normalised plate coordinates. "
            "eyes/mouth/hat are single sprites per trait, so the compositor "
            "transforms them onto each body's head using this table. Values are "
            "hand-annotated from the art and verified with "
            "scripts/build_rig.py --sheet. Rendering config only: it is NOT part "
            "of the traits/weights/tiers bundle hash the fairness pipeline uses."
        ),
        "config_name": "rig",
        "version": "1.0.0",
        "canonical": asdict(CANONICAL),
        "face_layers": dict(FACE_LAYERS),
        "sources": {k: asdict(v) for k, v in sorted(ANNOTATIONS.items())},
        "plates": {k: asdict(v) for k, v in sorted(plate_anchors().items())},
    }


def write_rig(path: Path | None = None) -> Path:
    path = path or RIG_PATH
    path.write_text(json.dumps(build_doc(), indent=2) + "\n", encoding="utf-8")
    return path


def load_rig(path: Path | None = None) -> dict:
    return json.loads((path or RIG_PATH).read_text(encoding="utf-8"))


def anchor_for(plate: str, doc: dict | None = None) -> Anchor:
    doc = doc or load_rig()
    return Anchor(**doc["plates"][plate])


def canonical_from(doc: dict) -> Anchor:
    return Anchor(**doc["canonical"])
