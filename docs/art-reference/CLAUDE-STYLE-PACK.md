# Claude Style Pack — match `ships_amano/`

**Goal:** final ship art should match `ships_amano/` at visual parity
(Final Fantasy VII–era Yoshitaka Amano cover quality). Ship-only first —
**no characters in boats** until the vessel style is locked.

**Current production path:** polished full-composition ship plates
(`scripts/install_polished_ships.py` → `sprites/ship_class/`), not the old
procedural stick-figure placeholders.

This pack is the short, operational prompt grammar. Full narrative lives in
[ART-DIRECTION.md](./ART-DIRECTION.md).

## One-line target

**Tattoo-clean Yoshitaka Amano ink: bone-white ground, dense calligraphic
linework, vertical warm→navy colour ramp on the ink itself, selective crystal
fills, flowing wave ribbons — not flat geometric posters.**

## Do (ships_amano DNA)

| Trait | Spec |
|---|---|
| Ground | Pure white / bone `#f4f4f0`. Subject floats; no full-bleed sky block. |
| Ink colour | **Stroke** carries the gradient: crimson/coral/gold/green at the **top** of the subject → violet → deep navy/ink at the **bottom**. |
| Line quality | Anti-aliased, variable weight, organic, art-nouveau plate lines, filigree curls. |
| Density | High edge density (~11–20% of opaque pixels are ink edges). Silhouette readable at a glance. |
| Fills | Sparse. Crystals and occasional hull shadow only. **Never** a solid navy silhouette ship. |
| Water | Parallel flowing ribbons / Hokusai-like crests — open white between strands. |
| Crystals | Faceted gems (hex/blade clusters) are a recurring motif on capital ships. |
| Character | Profile/¾ amphibian everyman, single large eye, tousled black hair, gold filigree collar, body dissolving into tendrils/water; curling smoke as composition flourish. |
| Mood | Melancholic JRPG elegance — salvage, not cartoon comedy. |

## Do not

- Flat vector blocks, chunky pixel silhouettes, or “game UI icon” ships
- Full-canvas vertical gradient backgrounds that paint the whole square
- Solid dark navy hulls with no interior linework
- Thick black outlines without the red→navy ramp
- Photoreal 3D ships, metal PBR, or generic AI “fantasy ship” stock look
- Tracing or copying a specific reference composition (style only — Risk 2)

## Measured targets (`scripts/style_score.py`)

| Metric | Target | Meaning |
|---|---|---|
| `white_ground` | ≥ 0.75 | Most of the frame is near-white |
| `edge_density` | ≈ 0.15 | Ink lines, not fills |
| `vertical_ramp` | ≥ 0.65 | Cooler/bluer as you go down the subject |
| `dark_fill` | ≤ 0.12 | Avoid large solid dark masses |
| `mean_luma_opaque` | ≥ 0.72 | Overall bright composition |

Golden refs currently self-score ~85–100% mean. Composites under test must
reach **92% mean overall**.

## Prompt skeleton (image models / Claude art)

```
Amano-style ink illustration on pure white background. Ornate [SHIP CLASS]
as flowing calligraphic line art with dense art-nouveau plate filigree.
Vertical colour ramp on the ink: [TOP HUE] at the top of the subject fading
through violet into deep navy at the keel. Faceted crystal cluster growing
from the superstructure. Flowing ribbon waves, open white between strands.
No flat fills, no full-bleed sky, no solid silhouette. Tattoo-clean,
melancholic, elegant. Anti-aliased fine lines.
```

Ship-class cues (from `ships_amano/`):

- **Battleship** — organic armor plating, triple gun turrets, crystal crown, coral→navy ramp.
- **Aircraft carrier** — long deck, island tower, chevron jets, crystal cluster held or erupting, red→navy.
- **Blockchain ship** — mesh/network sails (nodes + edges), chains, floating cubes, crystal masts, crimson or chia-green → navy.
- **Pirate ship** — multi-mast billowing sails, crescent-moon filigree, ribbon waves (see `pirate-ship/`).

Character cue (from `tom-bepe-amano/`):

```
Original amphibian sailor (not Pepe): refined frog proportions, one large
expressive profile eye, gentle half-smile, tousled Amano black hair, ornate
gold filigree collar, modern jacket in flowing ink folds, lower body dissolving
into water tendrils. Optional curling smoke in the same red→navy ramp.
White ground, line-art dominant.
```

## Layer production rules (compositor)

Layers are **transparent PNG** at `render.json` illustration `master_px` (2048).
They composite onto a **bone-white** canvas (`render_engine.compose`).

| Layer | Draw |
|---|---|
| sky | Barely-there wisps / disc outline only — never a solid fill |
| sea | Wave ribbons only |
| ship_class | Full ornate vessel + crystals + class motifs |
| ship_condition | Overlay ink (fire smoke, flood ribbons, ghost veil, cracks) |
| body / clothing / eyes / mouth / hat | Gestural line figure, gold collar, hair |
| aura | Swirl + smoke flourishes |
| scene_element | Distant filigree structures / crystals / moon |

## Local loop (ship-only, current)

```bash
# Install polished plates from ships_amano + output/amano_polish/
# (blanks character / sky / sea layers so composites are ship-only)
python scripts/install_polished_ships.py

# Review contact sheet + per-ship showcases
#   output/style_loop/contact_ships.jpg
#   output/style_loop/ship_*_512.png

# Score vs ships_amano golden set
python scripts/style_score.py --samples output/style_loop/ship_*_2048.png --threshold 100
```

**Hierarchy of fidelity**

1. **Use authentic `ships_amano/` files** for Battleship / Blockchain Ship when
   they fit (they *are* the style).
2. **image_edit from those refs** for other classes — always multi-ref the
   golden set; demand pure line art, no cel fills, no people, no text/logos.
3. Never ship the old PIL stick-figure placeholders as style targets.

When replacing art, keep **filename**, **2048×2048**, and **RGBA** conventions.

## Provenance

`ships_amano/` is owner-supplied style direction for capital ships (2026-07).
References are **not** redistributed as mint art. Adapt grammar only.
