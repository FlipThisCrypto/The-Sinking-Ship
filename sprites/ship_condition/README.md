# sprites/ship_condition — Ship Condition

z-order: 5 | required: True | dimensions: 2048x2048 RGBA PNG (illustration profile)

> **PRODUCTION ART** — authored by `engine/artgen/ship_condition.py`,
> regenerate with `python scripts/gen_art.py --layer ship_condition`.
> Originals frozen in [`vault/sprites-v1/`](../../vault/README.md).

## The problem this layer solves

Eleven conditions must read correctly over **sixteen structurally unrelated**
ships — a raft, a submarine, an aircraft carrier — sharing no hull line, mast
position or deck height. The trait contract is one sprite per condition, so an
overlay cannot know what is underneath it. A fixed hull-shaped decal is exactly
how you get a mess pasted on a mess.

Three devices avoid that:

1. **Water is ship-agnostic.** `listing`, `half_sunk` and `fully_underwater`
   are *waterline* events, not hull events. Raised water at a given height
   looks right over any hull, and `water_alpha < 0.8` keeps the ship reading
   through the surface instead of being blotted out. The raised water is a
   local **swell** that relaxes back to the sea layer's own horizon at the
   frame edges — a full-width plane at a different height would put two
   contradictory horizons in one picture.
2. **Damage follows measured occupancy.** `ship_occupancy()` measures where ink
   actually falls across all sixteen ship plates; flames, rifts, scaffolding
   and salvage rigging sample that field, so marks land on ship structure for
   most classes rather than hanging in open water.
3. **The ghost echo is derived, not drawn.** The spectral double *is* the
   occupancy silhouette, so it approximately traces whatever hull it covers.

## Coordinates

This layer has **no** `layer_transforms` entry in `config/render.json`, and
must not gain one: water has to reach the frame edges, and a transform would
confine it to the ship's 0.8 box and render it as a hard rectangle mid-frame.
The renderer instead reads `ship_class`'s transform from config and maps
ship-plate points into canvas space itself (`ship_to_canvas`).

`SEA_HORIZON` (0.58) is shared with the sea layer; the point where it crosses
the ship, `canvas_waterline_in_ship_space()` = 0.525, is derived from the
transform rather than hand-tuned.

**Dependency:** this layer samples the `ship_class` art. If those plates change,
regenerate these too — `tests/test_artgen_reproducible.py` will flag the drift.

| file | trait |
|---|---|
| `floating.png` | Floating |
| `listing.png` | Listing |
| `half_sunk.png` | Half Sunk |
| `flooded.png` | Flooded |
| `broken_mast.png` | Broken Mast |
| `burning.png` | Burning |
| `being_salvaged.png` | Being Salvaged |
| `split_hull.png` | Split Hull |
| `fully_underwater.png` | Fully Underwater |
| `ghost.png` | Ghost |
| `rebuilt.png` | Rebuilt |
