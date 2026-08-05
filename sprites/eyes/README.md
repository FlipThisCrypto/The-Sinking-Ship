# sprites/eyes — Eyes

z-order: 8 | required: True | dimensions: 2048x2048 RGBA PNG (illustration profile)

> **PRODUCTION ART** — authored by `engine/artgen/eyes.py`, regenerate with
> `python scripts/gen_art.py --layer eyes`. Originals frozen in
> [`vault/sprites-v1/`](../../vault/README.md).

## Authored in canonical rig space

Drawn once against `rig.CANONICAL` — eye at (0.520, 0.145), head height 0.190 —
and landed on each body by `render_engine._place_face`. See the rig section of
[`sprites/README.md`](../README.md).

## Two rules

**One eye, not two.** `ART-DIRECTION.md` names *a single large expressive eye
in profile* as the species cue, and the body plates disagree about how many
eyes are visible. So the rig anchor is the **dominant** eye — the only one on a
profile head, the nearer and larger one where two are drawn — not the centre of
the eye mass. Anchoring on the midpoint of a two-eyed face put the sprite on
the bridge of the nose.

**The eye occludes; it does not overlay.** The body already has an eye drawn at
this spot, so every trait lays down an opaque bone-white eye body before inking
its state onto it. That shape is always drawn at *full* extent even when the
lid is down: shrinking it with the lid left the body's open eye showing around
a sliver of closed lid, which is the exact artefact this layer exists to
prevent. The eye is ~0.63 of head height — sized to cover the art beneath, and
matching the reference character's very large eye.

| file | trait |
|---|---|
| `normal.png` | Normal |
| `sleepy.png` | Sleepy |
| `closed.png` | Closed |
| `determined.png` | Determined |
| `scared.png` | Scared |
| `crying.png` | Crying |
| `hopeful.png` | Hopeful |
| `looking_to_horizon.png` | Looking to Horizon |
| `dead.png` | Dead |
| `heart.png` | Heart |
| `laser.png` | Laser |
| `middle_finger_pupils.png` | Middle Finger Pupils |
| `pixel_stars.png` | Pixel Stars |
| `wizard.png` | Wizard |
| `diamond.png` | Diamond |
| `xch.png` | XCH |
