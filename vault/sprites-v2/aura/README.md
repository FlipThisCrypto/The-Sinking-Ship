# sprites/aura — Aura / Effect

z-order: 11 | required: False | dimensions: 2048x2048 RGBA PNG (illustration profile)

> **PRODUCTION ART** — authored by `engine/artgen/aura.py`, regenerate with
> `python scripts/gen_art.py --layer aura`. Originals frozen in
> [`vault/sprites-v1/`](../../vault/README.md).

## Two constraints in tension

**Spectacular.** Only ~8% of supply carries an aura and every trait sits in the
epic/legendary/mythic buckets, so a buyer who rolls one should see it at
thumbnail size.

**Must not bury the face.** This is the last layer composited — it draws over
eyes, mouth and hat. So emission is built as *rim light*: a soft annulus around
the figure rather than a disc over it, plus `face_guard_mask()`, which pulls
alpha down inside the head ellipse. Measured on the shipped plates, the
rim-light traits carry 0.31–0.67× as much alpha over the face as around it.

`halo_light` and `laser_bloom` are deliberate exceptions — a halo spills down
onto the face and the laser is aimed along the eye line — so they carry a
weaker guard and are excluded from the rim-light test, but they are still held
to the absolute "never opaque over the features" bound.

## Geometry

Measured, not guessed. Compositing the body plate at scale 0.84 anchored to the
bottom puts the figure at canvas y 0.16–1.0 with horizontal centre of mass at
x 0.519 and head mass peaking near y 0.33 — hence `FOCUS = (0.52, 0.33)` and
`TORSO = (0.52, 0.58)`.

| file | trait |
|---|---|
| `green_magic_glow.png` | Green Magic Glow |
| `purple_magic_glow.png` | Purple Magic Glow |
| `crystal_shimmer.png` | Crystal Shimmer |
| `halo_light.png` | Halo Light |
| `laser_bloom.png` | Laser Bloom |
| `ghost_fade.png` | Ghost Fade |
| `golden_radiance.png` | Golden Radiance |
| `chia_bloom.png` | Chia Bloom |
| `corruption_static.png` | Corruption Static |
