# sprites/ship_class — Ship Class

z-order: 4 | required: True | dimensions: 2048x2048 RGBA PNG (illustration profile)

> **EXTERNALLY AUTHORED — REPAIRED, NOT REGENERATED.** These 16 illustrations
> were produced outside this repository and have no generator here. Defects are
> corrected in place by `scripts/repair_art.py`; the pre-repair files are
> byte-exact in [`vault/sprites-v1/`](../../vault/README.md).

## Repairs applied

**Residual white matte removed** (`--unmatte`, all 16 plates). Three plates —
`lifeboat`, `raft`, `luxury_yacht` — carried a near-white film across the
*entire* canvas; `lifeboat` reached alpha 148/255 in a corner. Invisible on
bone white, but composited over a coloured sky it bleached a 2048x2048
rectangle with a hard edge. The repair reconstructs true straight alpha from
the ink-on-white model (`alpha = 1 - min(RGB)/255`), which reproduces the
plate's appearance over white to within 1/255 while making paper genuinely
transparent. Side effect: the layer shrank 60.0 MB -> 44.6 MB, because
transparent pixels no longer carry noisy RGB.

Authored transparency is preserved — several plates carry dark leftover RGB
under `alpha == 0` (`aircraft_carrier` down to 0) and deriving alpha from
colour alone would paint that ink back in.

| file | trait |
|---|---|
| `raft.png` | Raft |
| `lifeboat.png` | Lifeboat |
| `fishing_boat.png` | Fishing Boat |
| `tug_boat.png` | Tug Boat |
| `cargo_ship.png` | Cargo Ship |
| `steam_ship.png` | Steam Ship |
| `luxury_yacht.png` | Luxury Yacht |
| `cruiser.png` | Cruiser |
| `battleship.png` | Battleship |
| `aircraft_carrier.png` | Aircraft Carrier |
| `submarine.png` | Submarine |
| `pirate_ship.png` | Pirate Ship |
| `ghost_ship.png` | Ghost Ship |
| `the_ark.png` | The Ark |
| `wizard_ship.png` | Wizard Ship |
| `blockchain_ship.png` | Blockchain Ship |
