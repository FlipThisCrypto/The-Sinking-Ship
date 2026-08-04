# sprites/sea — Sea

z-order: 2 | required: True | dimensions: 2048x2048 RGBA PNG (illustration profile)

> **PRODUCTION ART** — authored by `engine/artgen/sea.py`, regenerate with
> `python scripts/gen_art.py --layer sea`. Deterministic and
> resolution-independent. Originals frozen in
> [`vault/sprites-v1/`](../../vault/README.md).

## Composition contract

- **A band, not a floor.** Alpha rises at the waterline (`HORIZON` 0.58, shared
  with `sky`), carries the lower third, and dissolves before the bottom edge.
  The reference art floats its vessels on a belt of churning ink over
  bone-white, and the character's lower body dissolves into water tendrils
  across the bottom-centre — a filled sea there turns the composite to mud.
- **Ragged hem.** The lower fade is displaced per-column by low-frequency
  noise. A ruled horizontal edge is the most artificial thing a hand-drawn sea
  can do.
- **Broken swells.** Each row is 2–4 partial-width `flow_bundle` segments with
  their own phase and offset, not one full-width curve — a constant-y line
  across the frame reads as a contour on a topographic map.
- **Perspective.** Rows compress and thin toward the horizon (`t ** 1.55`),
  widen and thicken toward the viewer. Evenly spaced rows read as wallpaper.
- The plate never paints above the waterline; `sky` owns everything up there.

| file | trait |
|---|---|
| `calm.png` | Calm |
| `storm_swell.png` | Storm Swell |
| `black_sea.png` | Black Sea |
| `frozen.png` | Frozen |
| `emerald_water.png` | Emerald Water |
| `red_water.png` | Red Water |
| `whirlpool.png` | Whirlpool |
| `glass_sea.png` | Glass Sea |
| `abyss.png` | Abyss |
| `bioluminescent.png` | Bioluminescent |
| `chia_green_tide.png` | Chia-Green Tide |
