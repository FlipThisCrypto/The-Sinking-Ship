# sprites/sky — Sky

z-order: 1 | required: True | dimensions: 2048x2048 RGBA PNG (illustration profile)

> **PRODUCTION ART** — authored by `engine/artgen/sky.py`, regenerate with
> `python scripts/gen_art.py --layer sky`. Deterministic: the same trait key
> always produces byte-identical output. Originals frozen in
> [`vault/sprites-v1/`](../../vault/README.md).

## Composition contract

Every plate obeys the same rules so the 15 traits stack interchangeably under
the other ten layers:

- **Atmosphere, not a block.** Alpha peaks in the upper third and reaches zero
  just past the shared `HORIZON` (0.58), so the `sea` plate seats without a
  seam and the bone-white ground breathes through the middle. Mean alpha runs
  0.10–0.27; `MAX_ALPHA = 0.86` is a hard ceiling.
- **Gradient on the stroke.** Colour comes from a vertical ramp; the same
  warped-fBm field drives both the wash and — via `ink.contour_strokes` — the
  cloud linework, so form and edge always agree.
- **One signature motif per trait**, legible at 128 px: the rarity has to read
  in a marketplace thumbnail, not only at full size.
- Restraint scales with rarity: `calm_blue` and `overcast` (common) are the
  quietest plates in the set; `solar_eclipse` (legendary) is the loudest.

| file | trait |
|---|---|
| `calm_blue.png` | Calm Blue |
| `overcast.png` | Overcast |
| `orange_sunset.png` | Orange Sunset |
| `golden_sunset.png` | Golden Sunset |
| `moonlit.png` | Moonlit |
| `heavy_rain.png` | Heavy Rain |
| `fog.png` | Fog |
| `lightning.png` | Lightning |
| `purple_storm.png` | Purple Storm |
| `aurora.png` | Aurora |
| `green_aurora.png` | Green Aurora |
| `meteor_shower.png` | Meteor Shower |
| `blood_moon.png` | Blood Moon |
| `fire_sky.png` | Fire Sky |
| `solar_eclipse.png` | Solar Eclipse |
