# ADR-0002 — Deterministic RNG: HMAC-SHA256 DRBG over named substreams, integer-only draws

**Status:** Accepted
**Date:** 2026-07-09

## Context

Spec 5.4 requires chest rolls seeded by `HMAC(secret_salt, payment_coin_id)`,
recomputable by anyone after the salt reveal. The mission's hardest
requirement: identical inputs must produce **byte-identical manifests across
runs and machines**. Candidate RNGs:

1. `random.Random(seed)` — Mersenne Twister. Stable in practice, but its
   float-based `choices`/`shuffle` paths and Python-version coupling make
   "bit-identical forever, everywhere" a promise we can't prove.
2. `numpy` Generator — fast, but adds a binary dependency to the *fairness*
   path and has had cross-version behavior changes.
3. **Hand-rolled HMAC-SHA256 DRBG in counter mode, integer-only draws** —
   ~80 lines of stdlib, directly publishable as part of the provenance
   commitment.

## Decision

Option 3 (`engine/shipgen/drbg.py`, algorithm id `HMAC-SHA256-DRBG-v1`):

- `seed_key = HMAC-SHA256(salt, coin_id_bytes)` — coin id normalized
  (strip `0x`, lowercase, exactly 32 bytes) before hashing so formatting
  can never change a roll.
- Every draw site uses a **named substream**:
  `stream_key = HMAC(seed_key, label)`, blocks are
  `HMAC(stream_key, counter)`. Labels are stable strings
  (`"chest/quantity"`, `"slot/7/nft/0"`, `"chest/pity"`), so adding a new
  draw site never shifts existing draws — critical for verifier stability.
- Integers come from 8-byte chunks via **rejection sampling**; weighted
  choice walks integer milli-weight cumulative sums. **No floating point
  exists anywhere in the roll path** — weights are integer milli-units,
  luck and bias multipliers are integer permille. IEEE-754 questions
  simply cannot arise.
- Global randomness fixed at commit time (Torn slots, grail placements)
  derives from `HMAC(salt, "sinking-ship-commitment-root")` substreams.
- The commitment is `SHA-256` of the canonical JSON (sorted keys, compact
  separators, ASCII) of `{scheme, rng_algorithm, engine version,
  config_hash, placements, salt}`; the config bundle hash covers traits,
  weights, and tiers configs byte-exactly.

## Consequences

- The whole fairness core is auditable from one printed page; a third party
  can reimplement it in JS for in-browser verification (adopted from the
  reference repo's pure-engine pattern, ADR-0001).
- Rejection sampling costs ~1 extra HMAC per draw in the worst case —
  irrelevant at our scale (full-sellout simulation of ~44k NFTs runs in
  seconds).
- Any change to configs or algorithm invalidates the commitment by
  construction (hash changes), which is exactly the guarantee the fairness
  page needs.
- We deliberately accept writing ~30 lines of tests to prove determinism
  instead of trusting a library's stability promise.
