# ADR-0004 — Tier math and the supply model (and the spec's own overflow)

**Status:** Accepted (with open questions OQ-1/OQ-2/OQ-4 for the owner)
**Date:** 2026-07-09

## Context

Spec 5.2's tier table is extracted verbatim into `config/tiers.json`. Three
modeling decisions were not fully specified, and one arithmetic conflict
exists in the spec itself.

## Decision

1. **Chest quantity is uniform-inclusive over the tier range.** For every
   tier the spec's `E[mints]` equals the range midpoint (2–4→3, 8–12→10,
   230–270→250 …), which is exactly the uniform mean — so uniform is the
   distribution the spec's own arithmetic implies. Recorded as
   `chest_quantity_distribution: "uniform_inclusive"`.
2. **Depth Luck multiplies Epic+ bucket weights** (epic, legendary, mythic)
   as integer permille, per "multiplied odds on Epic+ rolls". Tier 10's
   "∞" luck is implemented as a finite 10.0× (OQ-2): infinity would make
   every trait roll Epic+, which contradicts the tier still producing a
   full 44-piece chest of mixed salvage; 10× is the strongest finite step
   above Admiral's 3×. Owner may override in tiers.json.
3. **Pity guarantees are chest-level floors** enforced deterministically:
   count qualifying NFTs (grails always qualify); for each missing
   qualifier, a DRBG-chosen non-qualifying NFT re-rolls with one
   DRBG-chosen carrier layer restricted to traits at/above the floor
   bucket. Explainable in one sentence on the fairness page, and exact.
4. **Grail seeding** (5 Admiral / 27 mid-tier / auction / Wizard) is fixed
   at commit time over `(tier, pass_ordinal)` slots — see ADR-0003. Spec
   conflict **OQ-4**: 5 + 12 + 27 = 44 leaves zero grails for tier 10's
   "guaranteed named Grail"; resolved as auction 12 → 11 pending ruling.
5. **Supply accounting**: grails seeded into Admiral chests replace rolled
   slots (E[supply] 1,250 = 5 × 250 counts them); the Wizard chest is
   44 rolled + 1 grail = 45, matching the spec row exactly.

## The overflow (OQ-1) — measured, not hidden

Full sellout expected consumption sums to **44,239** (the spec's own row
sums), but the hard budget is `44,444 − 444 reserve = 44,000`. The spec's
"~44,239 + 444 ≈ 44,444" is arithmetically 44,683. Measured by
`simulate.py --profile sellout` across seeds: consumption ≈ 44,200–44,400,
i.e. **~200–400 NFTs over budget at full sellout**.

The Scuttling (5.3) makes undersell the expected case, so this only bites
at ≥ ~99.5% sellout — but mint-day code must not have an undefined edge.
Options for the owner:

- **(a) shrink the reserve** to ≤ 200 at full sellout (cheapest, symbolic
  444 lost);
- **(b) trim passes** (e.g. Snorkeler 3,000 → 2,920 removes ~240 expected);
- **(c) hard-cap late chests** (last chests clamp to remaining budget —
  ugly for buyers, needs disclosure on the odds page).

Until ruled, the engine keeps rolling per spec and `simulate.py` prints the
overflow loudly on every run; the fulfillment daemon design (P7 stub)
reserves a `supply_budget` check hook.

## Consequences

- tiers.json is the single source of truth; weights.json carries copies of
  depth_luck/guarantees for P3-prompt compatibility, and the config loader
  fails hard on any divergence between the two.
- Revenue at full sellout computes to 3,409.90 XCH from config (deep-tier
  prices revised by the owner 2026-07-11: Shipwright 3.50, Harbormaster 5.50,
  Admiral 10.00, for a monotonic 0.100→0.040 effective-cost regression) —
  matching the spec's "~3,410" — so the 25/50/75% sellout scenario modeling
  asked for in spec 5.2 can run off tiers.json without new code.
- Every open question is a config edit away from resolution; no code
  changes needed for (a) or (b), one guarded branch for (c).
