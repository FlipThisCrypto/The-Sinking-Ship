# sprites/ — layer sprite trees

One directory per rendered layer from `config/traits.json` (the `pose`
dimension has no directory — it composes into `body/` filenames). Each layer
directory has its own README listing every required filename and the trait it
belongs to.

**Everything here is currently a generated PLACEHOLDER** (see
`scripts/gen_placeholder_sprites.py`): solid fills with an accent stripe and
a 3-px checker notch. Replace file-for-file with final art:

- 48×48 RGBA PNG, alpha strictly 0/255 (no partial transparency)
- colors from the 32-color master palette (`config/palette.json`) —
  `python engine/render_engine.py --validate-sprites` warns on drift
- filenames and dimensions must not change (they are the traits.json contract)

| layer | files | notes |
|---|---|---|
| sky | 15 | background top; snaps to zone sub-palette at render |
| sea | 11 | background bottom; snaps to zone sub-palette |
| scene_element | 40 | series-prefixed filenames (harbor_/military_/pirate_/wizard_/crystal_) |
| ship_class | 16 | |
| ship_condition | 11 | overlays |
| body | 48 | 8 variants × 6 poses, pre-composited: `{variant}_{pose}.png` |
| clothing | 14 | |
| eyes | 16 | |
| mouth | 10 | plus None (no file) |
| hat | 14 | includes `the_torn_halo_horns.png` (quota-only) |
| aura | 9 | plus None; top layer |
