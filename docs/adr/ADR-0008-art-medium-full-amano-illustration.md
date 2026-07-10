# ADR-0008 — Art medium: full Amano illustration (authorized spec override)

**Status:** Accepted — **owner decision 2026-07-10**, overriding the spec's
stated pixel format. Resolves OQ-11.

## Context

The master spec's headline format is *"48×48 master pixels, nearest-neighbor
upscale to 2048×2048 and 4000×4000, no anti-aliasing."* The owner subsequently
supplied reference art (`docs/art-reference/`) in a **Yoshitaka Amano-style
flowing ink-illustration** idiom — anti-aliased fine linework, gradient washes,
ornate filigree — and confirmed the minted NFTs should be that medium
(ART-DIRECTION.md, Path B).

Per the build rule "if code and spec disagree, the spec wins; if ambiguous,
stop and ask" — this was surfaced as OQ-11 rather than guessed, and the owner
has explicitly chosen the illustration medium. This ADR records the authorized
deviation and its consequences so the override is documented, not silent.

## Decision

**Minted art is full Amano-style illustration authored at native 2048×2048
and 4000×4000, with anti-aliasing and full alpha.** The spec's "48×48 master,
nearest-neighbor, no-AA" clause is superseded for the final art medium.

Crucially, this changes **only the rendering medium**. Everything that decides
*which* traits an NFT has and *how it is described and verified* is
medium-independent and stands unchanged:

| Component | Status under this decision |
|---|---|
| P2 traits.json (9-layer trait system, constraints) | **Unchanged.** An illustration still has a sky, sea, ship, body, clothing, eyes, etc. |
| P3 weights + simulate (rarity tuning) | **Unchanged.** Rarity is a property of the trait combination, not the pixels. |
| P5 chest_roller (HMAC determinism, commit/reveal, quotas, grails, pity) | **Unchanged.** The fairness core selects traits; it never touched pixels. |
| P6 metadata_gen (CHIP-0007) | **Unchanged** except `format`/dimensions describe the illustration; attributes are identical. |
| P4 render_engine | **Adapted.** Gains an `illustration` render profile: full-alpha layer compositing at native resolution, **no** alpha binarization, **no** palette snapping, **no** nearest-neighbor upscale. The original `pixel` profile is retained (for a possible hybrid pixel line, and because the profile is config-selected). |
| palette.json | **Unchanged** (already v2, reference-anchored). Now a soft colour *guide* for illustration rather than a hard snap target. |

Production model: the same **layered z-order compositing** stack (traits.json)
still drives assembly, but each layer sprite is a high-resolution,
anti-aliased Amano-style PNG. This keeps 44,400 combinations generatable from a
few hundred layer assets — the illustration is composited, not hand-drawn per
token. Grails remain hand-authored 1/1s.

## Consequences

- **Render engine** grows a `config/render.json`-driven profile switch; the
  illustration profile composites with real alpha and authors at target size
  (no upscale). `--validate-sprites` validates against the active profile's
  dimensions and stops flagging anti-aliasing / off-palette as errors in
  illustration mode.
- **Placeholders** are regenerated per-profile; the 48×48 pixel placeholders
  remain valid for the pixel profile, and a native-resolution placeholder set
  backs the illustration profile so the pipeline runs end-to-end today.
- **Art budget** (spec Section 7) is re-framed: ~300 layer assets are now
  illustration-quality PNGs, not 48×48 sprites — a larger per-asset effort.
  The layer *count* is unchanged; the per-asset craft is higher. Flag for the
  owner's production planning.
- **Determinism guarantees are untouched** — they never depended on the art.
  A holder still verifies their chest's *trait manifest* with
  `chest_roller.py verify`; the art is a downstream rendering of that manifest.
- **The spec document is now out of date on the format line.** This ADR is the
  authoritative override; the spec should be footnoted at Section 1 / Section 7
  when next revised. Marketing copy ("pixel art") must be updated too — the
  landing page currently says "pixel-art"; that wording needs an owner-approved
  swap to the illustration framing.
- **CHIP-0007** `format` stays `CHIP-0007`; image `data_hash` will commit to
  the rendered illustration. No metadata schema change.

## Alternatives (from OQ-11, not chosen)

- **Path A pixel-translate** (spec-literal): rejected by owner.
- **Path C hybrid** (pixel NFTs + Amano brand-world): not chosen, but the
  retained `pixel` render profile keeps it a one-flag option if the owner
  later wants a pixel side-line.
