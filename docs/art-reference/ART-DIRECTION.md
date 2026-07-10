# Art Direction — THE SINKING SHIP

Derived from the owner-supplied references in this folder
(`pirate-ship/`, `tom-bepe-amano/`) and the capital-ship golden set
**`ships_amano/`** (repo root), 2026-07-10. This is the authoritative
description of the intended look. Where it refines the spec's art notes, it
does so **within** the spec's mandate — medium decision **OQ-11** is resolved
in ADR-0008 (full Amano illustration).

**Operational prompt pack for production / Claude:**
[CLAUDE-STYLE-PACK.md](./CLAUDE-STYLE-PACK.md). Style acceptance is measurable:
`python scripts/style_score.py --threshold 92`.

## The one-line look

**Yoshitaka Amano-flavoured aquatic ink illustration: elegant, melancholic,
flowing linework with ornate filigree, a vertical colour gradient that lives
on the ink strokes (warm top → deep navy bottom), on a bone-white ground.**
Final-Fantasy-era JRPG melancholy — tattoo-clean, not a flat poster — rendered
as if drawn in one breath of brush ink.

## ships_amano visual grammar (primary ship canon)

The files in `ships_amano/` (Battleship, Aircraft Carrier, Blockchain Ship
variants) are the **style floor** for capital ships. Measured DNA:

| Property | ships_amano truth | Anti-pattern (old placeholders) |
|---|---|---|
| Ground | ~75% near-white | Full-bleed sky/sea colour blocks |
| Structure | Dense calligraphic edges (~15% edge pixels) | Flat geometric silhouettes |
| Colour | Gradient **on the stroke** red/coral/green → navy | Solid navy fills, grey posters |
| Detail | Filigree plating, crystals, mesh sails, ribbon waves | 3-rectangle hull + triangle sails |
| Fills | Selective (crystals, soft hull shadow only) | Opaque blocks |

Class signatures to preserve when authoring final art:

- **Battleship** — organic armor, gun turrets, crystal crown, coral→navy.
- **Aircraft carrier** — long deck, island tower, jets, crystal cluster, red→navy.
- **Blockchain ship** — network-mesh sails, chains, cubes, crystal masts.

Procedural stand-ins in `scripts/gen_placeholder_sprites.py` (illustration
profile) implement this grammar via `engine/shipgen/amano_ink.py` so composites
and contact sheets read as the right *medium* while real art is produced.

## Tom Bepe (character sheet, from references)

- **Species:** an original amphibian everyman — a refined frog/toad, **not**
  Pepe. Legally distinct (spec Risk 2): different proportions, a single large
  expressive eye in profile, gentle knowing half-smile, subtle scale/skin
  texture, webbed hands.
- **Hair:** black, tousled, wind-blown Amano hair with curling wisps — the
  most recognisable silhouette cue.
- **Wardrobe:** ornate **gold filigree collar** as the signature ornament;
  otherwise a modern hoodie/zip-jacket rendered in flowing folds. Gold is
  reserved for ornament and treasure-light accents.
- **Signature action:** smoking (cigarette/toothpick) with **ornate curling
  smoke** that becomes the composition's flourish. A "no smoke" variant set
  exists for cleaner moods.
- **Lower body:** frequently **dissolves into flowing water/tendrils** rather
  than resolving into legs — the character is of the wreck and the sea.
- **Palette on him:** the character often carries the zone gradient (green→navy
  for the Chia-coded/hopeful, crimson→navy for despair, gold→navy for
  treasure), with black hair and gold accents constant.

## World & environment style (the "background" note)

The placeholder backgrounds shipped in this session (flat solid blocks) are
**not** the target. Backgrounds should read like the reference ships and seas:

- **Flowing ink line-art** ships and waves — ornate, calligraphic, with
  curling wave-crests, filigree scrollwork, crescent moons, jolly-roger flags,
  and torn banners/ribbons.
- Rendered either as **pure gradient line-art on white** (sparse, tattoo-clean)
  or **full watercolour/ink** (green-and-navy washes, gold ornament) — the
  reference set spans both.
- Sea and sky are **atmosphere, not blocks**: gradients, ink washes, and
  linework, never flat fills.

## Colour system → depth

`config/palette.json` (v2.0.0) is re-anchored on these references. The
organising rule: **gradient hue encodes depth.**

| Zone | Gradient identity | Emotional beat |
|---|---|---|
| Surface | crimson / blood / fire on grey sky | despair |
| Sunlight | gold / amber | doubt |
| Twilight | violet (red meets navy) | loyalty |
| Midnight | deep navy + Chia-green | humour / brotherhood |
| Abyssal | ink + ember / bronze | building |
| Hadal | navy + green + gold light-below | hope |

Every top-gradient hue fades to **deep navy → ink** at the bottom. **Chia-green**
and **gold** are the recurring accents across all zones (Chia-coded pieces,
treasure light). White/bone is the ground.

## Mapping to the trait system

The 9 render layers (traits.json) are unchanged; the re-skin is a *style*
change, not a structural one:

- **sky / sea** — zone-gradient atmosphere + ornate wave linework (biggest
  departure from the placeholders).
- **ship_class / ship_condition** — the reference ships are the direct model:
  calligraphic hulls, filigree rigging; conditions (burning, ghost, rebuilt)
  as ink-wash overlays.
- **body (Tom Bepe × pose)** — the character sheet above; the 8 body variants
  are the zone gradient tints (Green, Blue, Zombie, Ghost, Gold, Emerald,
  Corrupted, Chrome).
- **clothing / eyes / mouth / hat** — the gold filigree collar, the big
  expressive eye set, the smoking mouth items, ornate hats (the Wizard/Admiral
  filigree, the Diver Helmet, the Halo/Horns "Torn").
- **aura** — the curling-smoke/ink flourish, tuned per aura trait.

## OQ-11 — RESOLVED: full Amano illustration (owner decision 2026-07-10)

**The owner chose Path B — full Amano illustration.** Minted art is
illustration authored at native 2048/4000 with anti-aliasing, not 48×48
pixel. This is an authorized override of the spec's pixel-format clause,
recorded in [ADR-0008](../adr/ADR-0008-art-medium-full-amano-illustration.md).
The trait system, rarity tuning, fairness core, and CHIP-0007 metadata are
medium-independent and unchanged; only the render medium changes (render_engine
gains an `illustration` profile). The paths below are retained for the record.

**The references are anti-aliased fine-line illustration. The spec mandated
48×48 masters, nearest-neighbour upscale, _no anti-aliasing_.** These are not
simultaneously satisfiable — Amano filigree cannot survive 48×48 hard-edged
pixels. The fork, as presented to the owner:

- **Path A — Pixel-translate (spec-literal).** Keep 48×48 no-AA pixel art;
  use the references as *mood, palette, subject, and silhouette* guides only.
  Tom Bepe becomes a chunky pixel frog carrying the gradient; ships become
  pixel ships. The entire render engine (P4) and fairness pipeline stay as
  built. Cheapest, on-spec, but sacrifices the Amano elegance.
- **Path B — Amano illustration (art-literal).** Abandon 48×48 pixel for
  hand/AI-assisted line-art at 2048/4000. Maximises the reference look but
  **replaces the spec's headline format and repurposes the P4 compositor**
  (traits/rarity/fairness core all still apply — only the sprite medium and
  the "no-AA pixel" mandate change).
- **Path C — Hybrid (recommended).** Pixel-art characters/ships as the minted
  NFT medium (keeps P4 + the whole deterministic pipeline intact and on-spec),
  with the flowing Amano linework driving the **website, lore-hero art, chest
  art, reveal effects, and marketing**. Buyers get crisp pixel salvage;
  the brand world wears the Amano coat. Lowest risk to the built engine,
  highest brand payoff.

## Tooling (style floor + measurement)

| Tool | Role |
|---|---|
| `engine/shipgen/amano_ink.py` | Shared ink primitives + vertical grade |
| `scripts/gen_placeholder_sprites.py --profile illustration` | Procedural stand-ins matching ships_amano grammar |
| `scripts/style_score.py --threshold 92` | Measure composites vs `ships_amano/` |
| `scripts/style_loop.py` | Regen sprites → sample → score in one shot |
| `render_engine.compose` (illustration) | Bone-white canvas + zone vertical ink grade |

Acceptance for a style batch: **mean overall ≥ 92%** on
`output/style_loop/` against `ships_amano/`. Golden refs self-score ~97%.

These placeholders are the **style floor** for Claude / human illustrators —
replace `sprites/**/*.png` file-for-file; re-run `style_loop.py` after each
batch so quality cannot silently regress.

## Reference provenance / licensing

The images in `ships_amano/`, `pirate-ship/`, and `tom-bepe-amano/` are
**style references only**, supplied by the owner. Per spec Risk 2 the shipped
art must be an original, legally distinct design: adapt mood, motif, and
palette — never trace or reproduce a specific reference. If any reference
carries third-party rights or a visible watermark, it must not be redistributed
as project art. Art-reference files under `docs/` are excluded from the mint
generation path; `ships_amano/` is the scoring golden set, not a sprite source.
