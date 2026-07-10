# ADR-0003 — Constraint engine: forward-biased sequential rolls + deterministic rejection + pre-committed quota slots

**Status:** Accepted
**Date:** 2026-07-09

## Context

Spec Section 3 defines exclusion/pairing rules ("the cohesion engine") that a
naive independent-per-layer roller cannot honor: cross-layer exclusions
(Ghost body ✕ Burning), cross-layer requirements (Fully Underwater → specific
seas), directional biases (Rebuilt → builder-coded traits), a correlated
cluster (any two wizard traits boost a third), a tier-gated combo
(Blood Moon + Ghost Ship + Skeleton Crew only on Mythic rolls), and a global
quota (exactly 44 Halo+Horns "The Torn"). All of it must run inside a
deterministic, seedable roll path (spec 5.4) — identical inputs must produce
byte-identical outputs on any machine.

Alternatives considered:

1. **Full constraint solver (CSP / backtracking).** Exact, but complex,
   hard to make audit-friendly, and overkill: our hard rules are sparse and
   involve at most 3 layers.
2. **Roll in z-order and patch violations after the fact.** Patching mutates
   distributions in opaque ways and is hard to explain in the fairness docs.
3. **Sequential rolls in a chosen order with forward-only biases, plus
   whole-NFT deterministic rejection for the few non-forward hard rules.**

## Decision

Option 3, with these mechanics:

- **`roll_order` is part of traits.json** (config, not code) and is chosen so
  every bias/pairing rule's `if` layer is rolled **before** its `then` layer:
  `body → ship_class → ship_condition → sky → sea → scene_element → clothing
  → eyes → hat → mouth → pose → aura`. Render z-order is separate and
  unaffected.
- **Hard exclusions/requirements whose `if` layer precedes the `then` layer
  are applied by candidate filtering**: when rolling the `then` layer, the
  excluded traits get weight 0 (or the required subset gets all the weight).
  No rejection needed, no distribution surprise.
- **Biases multiply weights** of target traits at roll time
  (`weight_multiplier` from config). The wizard **cluster** rule counts
  already-rolled cluster traits; once ≥ `min_present` (2) are present, the
  remaining cluster traits' weights are multiplied.
- **Non-forward or multi-layer rules use whole-NFT rejection**: after all
  layers roll, hard checks run (The Ark's any-of weather rule; the Mythic
  combo gate). On violation the entire NFT re-rolls with the next
  deterministic subseed (`nonce+1`). Rejection counts are bounded in practice
  (violating combos are rare-trait intersections; measured retry rate is
  well under 0.1%) and the loop is capped at 64 attempts with a hard error —
  a cap that has never been approached in simulation.
- **The Torn quota cannot be enforced per-chest** (chests roll independently;
  a global "exactly 44" needs global coordination). Instead, 44 **global mint
  indices** in [1, 44400] are derived from `HMAC-SHA256(salt,
  "the-torn-slots-v1")` at commit time and included (hashed) in the
  provenance commitment. An NFT whose global mint index lands on a slot has
  its hat overridden to The Torn. Grail seeding works the same way over
  (tier, pass_ordinal) slots. Consequence under The Scuttling: if the mint
  undersells, slots beyond the final minted count never occur, so realized
  Torn count can be < 44 (open question OQ-3 for the project owner).
- **Mythic forced aura** (spec 4.1) is a post-roll rule: if any rolled trait
  is Mythic-bucket, the aura layer re-rolls restricted to non-None auras
  (deterministic subseed), satisfying "Mythic = ≥1 Mythic trait + forced
  aura" without inflating aura rates elsewhere.

Determinism guarantees for all of the above: every random draw comes from a
per-NFT HMAC-DRBG stream (ADR-0002); layers roll in the fixed `roll_order`
list; candidate lists come from config arrays (never dict iteration);
rejection uses an explicit nonce ladder.

## Open interpretation questions

- **OQ-10 — "Ghost body forces Ghost Fade aura eligibility" (spec 3).** This
  is encoded as an 8× weight *bias* (`p_ghost_body_ghost_fade`), so Ghost Fade
  can still appear on non-Ghost bodies at its base rate. If "eligibility" was
  meant as *exclusivity* (Ghost Fade allowed **only** on Ghost bodies), it
  should instead be a hard gate (exclude Ghost Fade unless body = Ghost). Both
  readings are defensible; flagged for the owner. Changing it is a one-line
  config edit (convert the `bias` rule to an `exclude`-family rule) plus a
  simulation re-run — no engine change.

## Consequences

- The published fairness page can explain the whole engine in four sentences
  (ordered rolls, weight multipliers, re-roll on illegal combos, pre-drawn
  quota slots) — auditors can reimplement it from the docs.
- Rejection sampling slightly reshapes marginal distributions; this is
  absorbed by the Monte Carlo weight-tuning loop (P3), which tunes through
  the *real* roller, not an idealized model.
- The Torn/grail slots being index-based makes the roll command require the
  chest's `pass_ordinal` and global `start_index` — supplied by the
  fulfillment daemon (P7) and published in the post-mint ledger so verifiers
  can recompute everything.
- Adding a new pairing rule is a config edit + simulation re-run; no code
  changes unless a genuinely new constraint *type* is invented.
