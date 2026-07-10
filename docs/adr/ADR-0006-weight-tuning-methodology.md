# ADR-0006 — Weight tuning: generated weights, sellout-mixture objective, replicated acceptance

**Status:** Accepted
**Date:** 2026-07-10

## Context

Spec 4.2 gives per-trait bucket base weights; spec 4.1 gives collection-level
tier counts the 44,444-run Monte Carlo must hit within ±5%. Three problems:

1. Raw base weights don't compose: with 12 rolled layers each carrying
   uncommon+ traits, P(all-common NFT) collapses to ~0 instead of 42.8%.
   Per-layer scaling is mathematically unavoidable.
2. The spec is silent on whether 4.1 describes the *luck-free* generator or
   the *final minted collection* (whose deep tiers roll with Depth Luck
   1.1×–3×).
3. The mythic tier has only ~400 expected members, so a single 44,444-run
   Monte Carlo carries √400/400 ≈ 5% Poisson noise at 1σ — a single-run
   ±5% acceptance gate would fail ~1 time in 3 on a *perfectly tuned*
   generator.

## Decision

- **weights.json is a generated artifact** (`scripts/tune_weights.py`),
  committed like source. Per-trait weight = spec base weight × one global
  scale per bucket, in integer milli-units; each optional layer's None share
  is held at a documented design value (scene 60%, mouth 40%, hat 25%,
  aura 92.5% → ~8% aura rate per spec 3.11). Re-running the tuner is
  deterministic (fixed seeds) and reproduces the file byte-for-byte.
- **Tuning objective = the full-sellout mixture** (OQ-5 decision): 4.1 is
  read as describing the collection buyers actually end up holding, which
  is minted through luck-bearing tiers — so tier probabilities are weighted
  by each tier's expected generated supply at its Depth Luck. The luck-free
  distribution is still reported by `simulate.py --profile flat` for
  transparency.
- **Two-stage calibration:** an analytic independence model (fast, no MC
  noise) converges the scales to ~0.1%, then a polish loop through the
  *real* roll engine — constraints, rejection re-rolls, pity upgrades,
  quota/grail overrides included — verifies and corrects residual bias on
  replicated full-sellout runs. Achieved centering, measured over 10
  replicates (~442k NFTs): worst tier +0.56%, mythic +0.02%.
- **Acceptance protocol uses replicate averaging:**
  `simulate.py --replicates 5 --check` gates on the 5-run average
  (σ_mythic ≈ 2.2%, so ±5% is a ≥2σ bound). The single-run noise reality
  is documented in the CLI help so nobody mistakes one unlucky draw for a
  broken generator.

## Authoritative artifact vs. diagnostics

The `weights` block in `weights.json` is the **authoritative** committed
artifact — the provenance commitment (ADR-0002) hashes it byte-exactly, and
all rolls read it directly. The `bucket_scales_permille` field is a
human-readable, **display-rounded** diagnostic and must NOT be used to
recompute the weights (permille rounding loses ~3–4% precision, so
`base × permille/1000` will not reproduce the committed per-trait values).
An in-browser or third-party verifier must read the `weights` block itself,
not re-derive it. The generator also emits `bucket_scales` (full-precision
`repr` of the float scales) so a re-run is exactly reproducible; the
committed v1.0.0 file predates that field, which is immaterial because the
`weights` block — not the scales — is what gets committed and rolled.

## Consequences

- Rarity is tunable by re-running one script after any config change; the
  polish report (measured distributions per iteration) is embedded in
  weights.json for auditability.
- The ±5% guarantee we can honestly publish is about the generator's
  *expected* distribution; per-run wobble on a 0.9% tier is physics, not a
  bug — the fairness page (P9) should state this plainly.
- If the owner rules OQ-5 the other way (targets apply to the luck-free
  generator), the tuner's mixture collapses to a single 1.0× entry — a
  one-line change with the same pipeline.
