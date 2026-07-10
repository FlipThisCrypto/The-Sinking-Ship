# ADR-0005 — Palette strategy and the non-integer upscale problem

**Status:** Accepted
**Date:** 2026-07-10

## Context

Spec Section 7: one 32-color master palette + six zone-specific 12-color
sub-palettes; every sprite snaps to the master, backgrounds snap to their
zone sub-palette. Spec Section 3 header: 48×48 masters upscaled to
2048×2048 and 4000×4000 with nearest-neighbor and no anti-aliasing.

Two decisions needed:

1. **Sub-palette relationship.** Independent 12-color palettes per zone
   would let zone art drift away from the master 32 — defeating "44k
   outputs look like one world."
2. **The upscale arithmetic.** 2048/48 = 42.67 and 4000/48 = 83.33 are not
   integers. A straight NEAREST resize to the exact spec sizes produces
   pixel columns of alternating 42/43 (or 83/84) screen pixels; an integer
   scale (42×=2016, 83×=3984) needs 32/16 px of padding to hit the spec
   dimensions.

## Decision

- **Sub-palettes are strict subsets of the master** (validated by schema +
  loader). Zone snapping applies to the `background_layers` listed in
  palette.json (sky, sea); all other layers snap to the full master. A
  zone-snapped sprite is therefore automatically master-compliant.
- Palette values are a working proposal anchored on the early Tom Bepe
  reference art (greens/olive/mustard) and the six zone moods (surface
  whites/oranges → hadal blacks/wizard-greens/gold). Swapping any hex in
  palette.json re-themes the whole pipeline; no code knows any color.
- **Default upscale mode is `exact`**: straight NEAREST to 2048/4000, per
  the spec's literal sizes. The 1-pixel column variance is < 2.4% of a
  cell and imperceptible at PFP sizes; marketplaces expect the stated
  dimensions. `--scale-mode integer` (42×/83× + symmetric transparent
  padding) exists for print/archival use. OQ-7 for the owner: if
  pixel-perfect uniformity matters more than full-bleed, flip the default.
- Alpha is binarized (≥128 → 255, else 0) at load time and `--validate-sprites`
  warns on any semi-transparent source pixel, so partial alpha can never
  reach an output even if art tools sneak it in.

## Consequences

- Final art can be authored against the master palette only; zone snapping
  of backgrounds is a render-time constraint, not an authoring burden.
- Because snapping happens at render time (with warnings at validation
  time), slightly off-palette source art degrades gracefully instead of
  blocking the pipeline — but the validator keeps the tree honest.
- The exact-mode upscale keeps files at the spec's exact dimensions at the
  cost of microscopically uneven pixel widths; documented so nobody
  "fixes" it into padded outputs (or vice versa) without a decision.
