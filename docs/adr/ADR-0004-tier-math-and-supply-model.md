# ADR-0004 — Tier math and the supply model (and the spec's own overflow)

**Status:** Accepted (OQ-1, OQ-2, OQ-4 resolved 2026-07-14)
**Date:** 2026-07-09 (updates 2026-07-14)

## Context

Spec 5.2's tier table is extracted into `config/tiers.json`. Three modeling
decisions were not fully specified, and one arithmetic conflict existed in
the spec itself.

## Decision

1. **Chest quantity is uniform-inclusive over the tier range.** For every
   tier the spec's `E[mints]` equals the range midpoint (2–4→3, 8–12→10,
   230–270→250 …), which is exactly the uniform mean — so uniform is the
   distribution the spec's own arithmetic implies. Recorded as
   `chest_quantity_distribution: "uniform_inclusive"`.
2. **Depth Luck multiplies Epic+ bucket weights** (epic, legendary, mythic)
   as integer permille, per "multiplied odds on Epic+ rolls".
3. **Pity guarantees are chest-level floors** enforced deterministically:
   count qualifying NFTs (grails always qualify); for each missing
   qualifier, a DRBG-chosen non-qualifying NFT re-rolls with one
   DRBG-chosen carrier layer restricted to traits at/above the floor
   bucket. Explainable in one sentence on the fairness page, and exact.
4. **Grail seeding** (5 Admiral / 27 mid-tier / auction / Wizard) is fixed
   at commit time over `(tier, pass_ordinal)` slots — see ADR-0003.
5. **Supply accounting**: grails seeded into Admiral chests replace rolled
   slots (E[supply] 1,250 = 5 × 250 counts them); the Wizard chest is
   44 rolled + 1 grail = 45, matching the spec row exactly.

## OQ-2 — Wizard Depth Luck — RESOLVED (2026-07-14)

**Ruling: finite 10.0×** (`depth_luck_permille: 10000`).

True ∞ would force every trait roll into Epic+ and erase mixed salvage in
the 44-piece Wizard chest. 10× is the strongest finite step above Admiral's
3× and is what marketing/odds pages must disclose (not "infinite rarity").

## OQ-4 — Auction grails 11 vs 12 — RESOLVED (2026-07-14)

**Ruling: auction = 11** (Wizard takes one from the auction pool).

Spec arithmetic `5 + 12 + 27 = 44` left zero room for tier 10's guaranteed
named grail while keeping the symbolic **44 grails**. Alternatives rejected:

- expand to 45 grails — breaks 44 symbolism;
- cut mid-tier (27) — hurts the "anyone can strike" hook;
- cut Admiral lottery (5) — worse for deep-tier buyers.

Placement: `5 Admiral + 11 auction + 27 mid + 1 Wizard = 44`.

## The overflow (OQ-1) — RESOLVED (owner 2026-07-14, option B)

**Problem (pre-ruling):** full sellout expected consumption summed to
**44,239**, but the hard budget is `44,444 − 444 reserve = 44,000`
(overflow **239**). The spec's "~44,239 + 444 ≈ 44,444" was arithmetically
44,683.

**Ruling:** **(b) trim passes** — Snorkeler `passes` **3,000 → 2,920**
(−80 passes × E[3] mints = **−240** expected NFTs). Expected full-sellout
consumption **44,239 → 43,999** (≤ 44,000 public mint budget). Full-sellout
revenue **3,409.90 → 3,389.90 XCH** (−20 XCH at 0.25 XCH/pass).

Alternatives not chosen:

- **(a) shrink the reserve** — would break the symbolic 444 treasury figure;
- **(c) hard-cap late chests** — buyer-hostile, needs odds-page disclosure.

**Residual:** chest-quantity variance can still push a *realized* full
sellout a few dozen NFTs around the mean. P7 fulfillment must continue to
refuse past `public_mint_budget` (fail closed). `simulate.py` only prints
OVERFLOW when measured consumption exceeds budget.

## Consequences

- tiers.json is the single source of truth; weights.json carries copies of
  depth_luck/guarantees for P3-prompt compatibility, and the config loader
  fails hard on any divergence between the two.
- Revenue at full sellout computes to **3,389.90 XCH** from config after the
  OQ-1 trim (deep-tier prices from 2026-07-11 unchanged: Shipwright 3.50,
  Harbormaster 5.50, Admiral 10.00 — monotonic 0.100→0.040 effective-cost
  regression). 25/50/75% sellout scenarios still run off tiers.json.
- OQ-1 / OQ-2 / OQ-4 closed by config + documentation; fulfillment budget
  gate remains mandatory for variance.
