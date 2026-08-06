# SPDX-License-Identifier: MIT
"""QA gates for the body layer.

The defect this layer existed to fix was a correctness bug with fairness
consequences: 48 filenames resolved to only 12 unique images, so distinct
trait combinations minted identical pictures. Most of these tests exist to keep
that from coming back.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from artgen import body  # noqa: E402

DIR = ROOT / "sprites" / "body"
PLATES = sorted(DIR.glob("*.png"))


@pytest.fixture(scope="module")
def digests() -> dict[str, str]:
    return {
        p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in PLATES
    }


# ------------------------------------------------------- the duplication bug


def test_all_48_body_plates_exist():
    assert len(PLATES) == 48


def test_every_body_plate_is_unique(digests):
    """The headline defect: 48 filenames, 12 images.

    "Blue Standing" and "Green Sitting" used to mint the same picture, so a
    buyer paying for a rarer combination received a duplicate.
    """
    seen: dict[str, list[str]] = {}
    for name, digest in digests.items():
        seen.setdefault(digest, []).append(name)
    collisions = {d: n for d, n in seen.items() if len(n) > 1}
    assert not collisions, f"duplicate plates: {list(collisions.values())}"


def test_each_variant_differs_across_all_six_poses(digests):
    for variant in body.VARIANTS:
        posed = {digests[f"{variant}_{pose}"] for pose in body.POSES}
        assert len(posed) == len(body.POSES), f"{variant} repeats a pose image"


def test_each_pose_differs_across_all_eight_variants(digests):
    for pose in body.POSES:
        tinted = {digests[f"{v}_{pose}"] for v in body.VARIANTS}
        assert len(tinted) == len(body.VARIANTS), f"{pose} repeats a variant"


# ------------------------------------------------------------- the contract


def test_keys_match_the_traits_cross_product():
    assert set(body.all_keys()) == body.expected_from_traits()


def test_every_key_maps_to_a_vaulted_source():
    for key in body.all_keys():
        src = body.VAULT_BODY / f"{body.source_for(key)}.png"
        assert src.is_file(), f"{key} -> missing source {src.name}"


def test_all_twelve_original_images_stay_in_service():
    """Nothing from the source art was discarded when deduplicating."""
    used = {body.source_for(k) for k in body.all_keys()}
    vaulted = {p.stem for p in body.VAULT_BODY.glob("*.png")}
    unique_originals = {
        hashlib.md5((body.VAULT_BODY / f"{n}.png").read_bytes()).hexdigest()
        for n in vaulted
    }
    used_originals = {
        hashlib.md5((body.VAULT_BODY / f"{n}.png").read_bytes()).hexdigest()
        for n in used
    }
    assert used_originals == unique_originals
    assert len(used) == 12


def test_sources_are_read_from_the_vault_not_the_live_tree():
    """Deriving from sprites/body/ would compound the grade on every run."""
    assert body.VAULT_BODY == ROOT / "vault" / "sprites-v1" / "body"
    assert "sprites/body" not in body.VAULT_BODY.as_posix()


def test_split_key_round_trips():
    for variant in body.VARIANTS:
        for pose in body.POSES:
            assert body.split_key(f"{variant}_{pose}") == (variant, pose)


def test_split_key_rejects_nonsense():
    for bad in ("", "green", "standing", "purple_standing", "green_flying"):
        with pytest.raises(KeyError):
            body.split_key(bad)


# ------------------------------------------------------------- the colourway


def test_colourways_use_only_master_palette_names():
    for key, way in body.COLOURWAYS.items():
        for stop in way.stops:
            assert stop in body.PAL, f"{key} references unknown colour {stop}"


def test_every_colourway_is_distinct():
    assert len({w.stops for w in body.COLOURWAYS.values()}) == len(body.COLOURWAYS)


def test_gradient_map_preserves_alpha_exactly():
    """The silhouette and every anti-aliased ink edge must survive untouched."""
    src = Image.open(body.VAULT_BODY / "green_standing.png").convert("RGBA")
    out = body.gradient_map(src, "gold")
    a_in = np.asarray(src)[:, :, 3]
    a_out = np.asarray(out)[:, :, 3]
    assert np.array_equal(a_in, a_out)


def test_gradient_map_preserves_tonal_ordering():
    """A darker pixel must stay darker: shading and line weight are the drawing."""
    src = Image.open(body.VAULT_BODY / "green_standing.png").convert("RGBA")
    out = np.asarray(body.gradient_map(src, "chrome")).astype(np.float32)
    ref = np.asarray(src).astype(np.float32)

    def luma(a):
        return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]

    vis = ref[:, :, 3] > 200
    li, lo = luma(ref)[vis], luma(out)[vis]
    idx = np.argsort(li)[:: max(1, li.size // 4000)]
    corr = np.corrcoef(li[idx], lo[idx])[0, 1]
    assert corr > 0.98, f"tonal ordering not preserved (r={corr:.3f})"


def test_ghost_reaches_a_true_dark():
    """A ramp that stops at grey vanishes into the bone-white composite ground."""
    stops = body.COLOURWAYS["ghost"].stops
    darkest = body.PAL[stops[-1]]
    assert max(darkest) < 120, f"ghost shadow end {stops[-1]} is too light"


def test_render_is_deterministic():
    a = np.asarray(body.render("gold_sitting", size=128)).tobytes()
    b = np.asarray(body.render("gold_sitting", size=128)).tobytes()
    assert a == b


def test_render_rejects_unknown_key():
    with pytest.raises(KeyError):
        body.render("mauve_standing", size=64)


# ------------------------------------------------------------ shipped plates


def test_all_plates_are_2048_rgba():
    for p in PLATES:
        img = Image.open(p)
        assert img.size == (2048, 2048), p.name
        assert img.mode == "RGBA", p.name


def test_transparent_pixels_carry_no_colour():
    for p in PLATES[::7]:
        arr = np.asarray(Image.open(p).convert("RGBA"))
        clear = arr[:, :, 3] == 0
        if clear.any():
            assert arr[:, :, :3][clear].max() == 0, p.name


def test_plate_file_sizes_are_bounded():
    """Body runs larger than the generated layers and that is inherent.

    RGB is ~3 MB of a ~3.5 MB plate even though only ~240 distinct colours are
    present: the source illustration's texture varies pixel to pixel, which
    defeats PNG's predictors. Palette encoding would cut it ~5x but shifts
    anti-aliased alpha by up to a full level, so it is not taken here.
    """
    worst = max(p.stat().st_size for p in PLATES)
    assert worst < 4_500_000, f"largest body plate is {worst} bytes"


# ------------------------------------------------- the pupil is removed


def test_body_derives_through_the_pupil_blanking_step():
    """The eyes layer supplies the pupil, so the drawn one must be gone.

    Without this the composite shows two pupils on every NFT that rolls an eye
    trait, which is what made the layer unusable.
    """
    from artgen import rig
    from artgen.repair import blank_for

    name = "green_standing"
    raw = Image.open(body.VAULT_BODY / f"{name}.png").convert("RGBA")
    blanked = blank_for(name, raw, rig.ANNOTATIONS[name])
    derived = body._blanked_source(name, raw.width)
    assert np.array_equal(np.asarray(derived), np.asarray(blanked))


@pytest.mark.parametrize("name", sorted(
    {"blue_back_turned", "blue_looking_down", "blue_on_bow", "blue_saluting",
     "blue_sitting", "blue_standing", "chrome_standing", "corrupted_standing",
     "emerald_standing", "ghost_standing", "gold_standing", "green_standing"}))
def test_the_drawn_pupil_is_actually_gone(name):
    """Measured, not assumed — via *flattening*, not brightness.

    Brightness is the wrong signal: the fill takes the iris colour, and it
    overwrites the sclera highlight as well as the pupil, so the mean moves up
    on some plates and down on others depending on how dark that character's
    iris is. What holds universally is that the eye's centre stops being a
    dark disc on a bright field and becomes one flat tone. Measured across all
    twelve sources the std ratio runs 0.22-0.72.
    """
    from artgen import rig

    a = rig.ANNOTATIONS[name]
    raw = np.asarray(
        Image.open(body.VAULT_BODY / f"{name}.png").convert("RGBA")
    ).astype(np.float32)
    out = np.asarray(body._blanked_source(name, raw.shape[0])).astype(np.float32)
    s = raw.shape[0]
    r = max(4, int(a.eye_w * s * 0.30))
    cx, cy = int(a.eye_x * s), int(a.eye_y * s)
    box = (slice(cy - r, cy + r), slice(cx - r, cx + r))
    before = raw[box][:, :, :3].mean(axis=2)
    after = out[box][:, :, :3].mean(axis=2)
    assert before.std() > 20, f"{name}: fixture has no pupil to remove"
    assert after.std() < before.std() * 0.80, (
        f"{name}: eye centre not flattened ({after.std():.1f} vs {before.std():.1f})"
    )


def test_blanking_leaves_the_rest_of_the_plate_alone():
    """Only the eye changes; the hand-drawn art everywhere else must survive."""
    from artgen import rig

    name = "gold_standing"
    a = rig.ANNOTATIONS[name]
    raw = np.asarray(
        Image.open(body.VAULT_BODY / f"{name}.png").convert("RGBA")
    ).astype(int)
    out = np.asarray(body._blanked_source(name, raw.shape[0])).astype(int)
    s = raw.shape[0]
    visible = raw[:, :, 3] > 8
    delta = (np.abs(raw - out).max(axis=2) > 12) & visible
    ys, xs = np.nonzero(delta)
    assert xs.size, "nothing changed"
    reach = max(np.abs(xs / s - a.eye_x).max(), np.abs(ys / s - a.eye_y).max())
    assert reach < a.eye_w * 3.0, "the edit escaped the eye"
    assert delta.mean() < 0.002, "too much of the plate changed"
