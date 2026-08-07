# sprites/eyes — Eyes

z-order: 8 | required: True | dimensions: 2048x2048 RGBA PNG (illustration profile)

> **PRODUCTION ART** — authored by `engine/artgen/eyes.py`, regenerate with
> `python scripts/gen_art.py --layer eyes`. Originals frozen in
> [`vault/sprites-v1/`](../../vault/README.md).

## What this layer draws — and what it does not

The **pupil**, plus a lid or an accent where the expression needs one. Nothing
else.

The body plates keep their own **iris, sclera, eyelid and socket**, all
hand-drawn; only their pupil is removed (see
[`sprites/body/README.md`](../body/README.md)). So the character's own eye goes
on doing the framing and the trait supplies the part that actually varies.

An earlier version drew a complete opaque eyeball over the top. It read as a
decal — a constructed shape sitting on a hand-drawn face — and correcting its
placement and scale did not help, because the problem was that it was replacing
better art than it could produce. `test_no_plate_paints_a_whole_eyeball` exists
to stop it growing back.

## Sizing

Authored against `rig.CANONICAL`: eye centre (0.520, 0.145), eye width 0.062,
which `eyes.EYE_W` must equal — the compositor scales by
`anchor.eye_w / canonical.eye_w`, so art drawn against a different width lands
wrong on every body.

`PUPIL_R` stays inside the disc `blank_pupil` clears (`0.34 * eye_w`).
Anything larger would overlap iris the artist drew and the composite would show
both.

A lid cannot be skin-coloured — this sprite has no idea which of the eight
colourways is underneath — so `closed` and `sleepy` are drawn in the
character's own idiom: a heavy ink lid with lashes, which reads over any skin
tone. Partial lids lean on the ink rim rather than the fill; at full strength
they read as a grey slab laid over the eye rather than a lid coming down.
