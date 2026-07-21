# The Wizard of the Deep — Puzzle Design Proposal (OPS-3)

> **Status: PROPOSAL — awaiting owner ratification.** This is a design starting
> point, not a locked mechanic, and it is an internal document. Do **not** reveal
> puzzle mechanics or the solution in marketing (the copy kit only *teases* the
> Wizard's existence). The owner owns the final creative and award decision;
> this exists to make that decision concrete and safe.

---

## 1. What the prize actually is

From `config/tiers.json`, the Wizard of the Deep is tier 10: **not for sale**
(`price_xch` is null), **1 pass**, a **44-NFT chest**, **10.0× Depth Luck**, and
a **guaranteed grail** (the single `wizard` grail from `grail_seeding`). So the
puzzle awards exactly one earned Hadal pass whose chest still rolls through the
same provably-fair engine as every other chest — the winner earns the *right to
dive*, not a hand-picked outcome. That distinction is the whole point and must
be preserved.

## 2. Design goals & non-negotiables

1. **Earned, never sold, never farmed.** No amount of money buys it; no bot army
   wins it. (Ties to [`HONOR-BADGE-SYSTEM.md`](HONOR-BADGE-SYSTEM.md) §4.)
2. **Provably legitimate.** Anyone should be able to verify *after the fact* that
   the winner was determined fairly and the chest rolled honestly — no "trust us"
   award. Reuse the commit–reveal machinery already built.
3. **On the lore.** The puzzle is a descent to the light below, not a generic
   ARG bolted on. It should read as canon (see the Hadal zone in the Lore Bible).
4. **Low-ops, hard to cheat.** A small team must be able to run and adjudicate it
   without a live service that can be gamed.
5. **No unfair information advantage.** The path must not require insider data or
   leak pre-reveal trait information about anyone's chest.

## 3. Proposed structure (three descents)

A staged puzzle mirroring the six depths, gated so each stage filters honestly:

- **Descent I — Sunlight (open, lore-gated).** A riddle seeded across the public
  lore drops and the site. Solvable by anyone paying attention; produces a
  passphrase, not a payment. Purpose: reward genuine engagement, wide funnel.
- **Descent II — Twilight/Midnight (skill + proof-of-personhood).** The Descent I
  passphrase unlocks a harder, multi-step challenge (e.g. reconstruct a
  fact from the fairness scheme — decode a value from the *published commitment*,
  which requires actually understanding commit–reveal, not brute force). Require a
  **signed wallet message** (`chia_signMessageByAddress`, already in the wallet
  flow) to bind a solution to a single identity — one entry per verified holder,
  cheap Sybil resistance without KYC.
- **Descent III — Hadal (the draw).** Among verified Descent-II solvers, the
  winner is chosen **deterministically from the revealed salt**, so the selection
  itself is provably fair and cannot be steered by the team:
  `winner_index = HMAC-SHA256(revealed_salt, "wizard-of-the-deep-v1") mod N`
  over the sorted list of qualifying wallet addresses. Publish the qualifier list
  hash *before* reveal so the set can't be edited after the fact.

This makes both halves auditable: *who qualified* (published, signed) and *who
won among them* (a public function of the same salt everyone already verifies).

### Alternative (simpler) if a puzzle is too heavy to run
A pure **provably-fair draw** among holders who completed one lore task and
signed a message — skip Descents I/II's difficulty, keep Descent III's
salt-derived selection. Less spectacle, same fairness and anti-Sybil properties.

## 4. Awarding the pass (operational)

1. Winner address is derived as above and announced with the derivation shown so
   anyone can recompute it.
2. The team issues the single Wizard Dive Pass offer to that address (0-XCH claim
   or a directed grant per the fulfillment flow).
3. The winner takes the offer; the chest rolls through `chest_roller.py` exactly
   like every tier — 44 NFTs, 10× luck, the guaranteed `wizard` grail — and the
   manifest is published and verifiable.
4. Record the whole chain (qualifier-list hash, salt, derivation, resulting
   manifest hash) in the mint decision log for permanent audit.

## 5. Anti-gaming checklist

- One entry per **signed** wallet; qualifier set hashed and published pre-reveal.
- Winner selection is a **public function of the revealed salt** — the team
  cannot pick a friend without it being detectable.
- No stage requires spending money, so it can't be pay-to-win.
- No stage exposes pre-reveal trait data.
- Timeboxed; late entries can't be inserted after the qualifier hash is published.

## 6. Open decisions for the owner

- **Difficulty/spectacle:** full three-descent puzzle vs. the simpler fair-draw
  alternative (§3).
- **Eligibility:** any wallet, holders only, or Salvage-Crew-only?
- **Count:** exactly one Wizard (matches the config), or reserve the mechanic for
  a small recurring honor later?
- **Timing:** during the mint window, or a post-Scuttling capstone event?
- **Puzzle content:** the actual riddles/lore embedding — owner-authored so it
  stays canon and unspoiled.

## 7. Why this is safe to build now

Everything here reuses primitives that already exist and are tested: the
commit–reveal salt, `signMessageByAddress` in the wallet flow, the fulfillment
offer path, and the decision log. No new trust assumptions, no new attack
surface on the mint itself. On owner ratification, the only net-new code is the
small, testable winner-derivation helper — which can ship with its own
determinism test alongside the existing fairness suite.
