# sprites/ — layer sprite trees

> The pre-revision originals are frozen byte-exact in
> [`vault/sprites-v1/`](../vault/README.md). `sprites/` always holds the
> **latest** art; the vault holds what it replaced. Check drift with
> `make vault`.

One directory per rendered layer from `config/traits.json` (the `pose`
dimension has no directory — it composes into `body/` filenames). Each layer
directory has its own README listing every required filename and the trait it
belongs to.

Contract for every file, whatever its status:

- 2048×2048 RGBA PNG (illustration profile, `config/render.json`)
- colours from the 32-colour master palette (`config/palette.json`) —
  `python engine/render_engine.py --validate-sprites` warns on drift
- filenames and dimensions must not change (they are the traits.json contract)
- RGB zeroed under `alpha == 0` — noisy transparent pixels defeat PNG
  filtering and inflate the layer by an order of magnitude

| layer | files | status | notes |
|---|---|---|---|
| sky | 15 | **production** (`artgen.sky`) | background top; atmosphere wash + cloud linework + per-trait motif |
| sea | 11 | **production** (`artgen.sea`) | background bottom; perspective wave band with a ragged hem |
| scene_element | 40 | **production** (`artgen.scene_element`) | five series (harbor_/military_/pirate_/wizard_/crystal_); distance-scaled, clears the ship's core |
| ship_class | 16 | externally authored, **repaired** | 16 distinct illustrations; residual white matte removed (`scripts/repair_art.py`) |
| ship_condition | 11 | **production** (`artgen.ship_condition`) | overlays; water keys off the waterline, damage off measured ship occupancy |
| body | 48 | **derived** (`artgen.body`) | 8 colourways × 6 poses from 12 vaulted originals; all 48 now distinct |
| clothing | 14 | empty stand-in | |
| eyes | 16 | **production** (`artgen.eyes`) | authored in canonical rig space; occludes the eye drawn on the body |
| mouth | 10 | empty stand-in | plus None (no file) |
| hat | 14 | empty stand-in | includes `the_torn_halo_horns.png` (quota-only) |
| aura | 9 | **production** (`artgen.aura`) | plus None; top layer — rim light with a face guard |

"Empty stand-in" is literal: `scripts/gen_placeholder_sprites.py` emitted a
fully transparent canvas for those layers, and all files in each are
byte-identical. They render as nothing.

## Face-layer registration (the body rig)

`eyes`, `mouth` and `hat` are single sprites per trait — `traits.json` gives
them no pose dimension — so one `eyes/normal.png` has to land correctly on all
48 body plates. Measured, the head moves a long way between them: **eye centres
span x 0.26 to x 0.83 and head height varies about 2.4x**. A fixed placement
puts the eyes on the cheek, or off the head, depending on the roll.

The plates cannot be normalised onto a shared rig without destroying their
composition (`blue_standing` and `emerald_standing` are different pictures, not
recolours), so the *face layers* are transformed per body instead:

- [`config/rig.json`](../config/rig.json) records an anchor per source image —
  dominant-eye centre, **eye width**, head height, facing — expanded to all 48
  plates. Face layers declare which measure scales them: `eyes` and `mouth`
  track `eye_w` (they are features), `hat` tracks `head_h` (it sits on the
  skull). One measure cannot serve both — eye-to-head ratio varies by more than
  2x across these plates. Values are **hand-annotated from the art and verified with
  a proof sheet**; two automatic detectors were tried and discarded (one had a
  confidence score inversely correlated with correctness; the other found a
  cigarette).
- `render_engine._place_face` composes two transforms: the rig, which maps the
  canonical head onto this body's head and mirrors it when the body faces the
  other way, then the body's own `layer_transform`, because the rig is in
  body-plate coordinates while the body is composited scaled and anchored.
- Face sprites are authored against `rig.CANONICAL` — eye at (0.520, 0.145),
  head height 0.190. No plate needs a scale outside 0.66x–1.74x.

Check it with `make rig`, which draws the anchors on each plate and lands a
registration card on all 48 bodies. `rig.json` is rendering config and is *not*
part of the traits/weights/tiers bundle hash the fairness pipeline uses.

## Authoring production art

`engine/artgen/` is the illustration engine; `scripts/gen_art.py --layer <name>`
writes a layer's final art.

- **Deterministic** — the same trait key always produces byte-identical bytes,
  so regenerating a layer produces no git churn unless the renderer changed.
- **Resolution-independent** — lengths are authored in master-reference pixels
  and scaled by the render context, so `--size 512` is a faithful preview of
  the 2048 master (and ~20× faster to iterate on).

```bash
python scripts/gen_art.py --layer sky                     # write the layer
python scripts/gen_art.py --layer sky --size 512 --dry-run --sheet /tmp/s.png
make art-verify                                           # committed art == renderers
```

A full layer regenerates in well under two minutes at 2048 (sky 15 plates
~78 s, sea 11 plates ~27 s). `tests/test_artgen_reproducible.py` re-renders
every committed plate and fails if one has drifted from its renderer — the
guard on the determinism promise above.
