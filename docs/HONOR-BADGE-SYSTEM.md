# THE SINKING SHIP — Honor Badge System (P11)

> How the crew earns recognition. Badges are **honor, not currency** — they mark
> conviction and contribution, and are designed so they cannot be bought,
> farmed, or flipped into a financial claim.

**Status:** complete design spec (P11). Community-ops document; nothing here
touches the mint/fairness engine. Voice and thesis per
[`docs/lore/LORE-BIBLE.md`](lore/LORE-BIBLE.md).

---

## 1. Principles

1. **Earned, never sold.** No badge is ever purchasable. Selling honor would
   turn it into the exact hype-token the project rejects.
2. **Recognition, not returns.** A badge confers standing and access to
   community rituals — never a promise of monetary value, allocation, or profit.
   (Same no-financial-claims rule as the copy kit.)
3. **Cheap to run, hard to fake.** Every mechanic must be low-cost for a small
   team to operate and expensive/annoying for a bad actor to game.
4. **On the lore.** Badges are salvage ranks and honors, not generic "points."
   They extend the six-depths world.
5. **Human in the loop for the rare stuff.** High honors require a human
   attestation, so they cannot be automated or Sybil-farmed.

---

## 2. Two kinds of recognition

Decide per honor whether it should be an **on-chain badge NFT** or an
**off-chain endorsement** (Discord role / signed attestation). Rule of thumb:

| Question | On-chain badge NFT | Off-chain endorsement |
|---|---|---|
| Must it be permanent & portable? | ✅ mint it | ❌ role is fine |
| Is it a one-time historic honor? | ✅ (e.g. First Divers) | — |
| Is it a revocable/ongoing status? | ❌ (revocation is ugly on-chain) | ✅ role |
| Could minting imply monetary value? | prefer off-chain | ✅ role |
| Is issuance high-volume/automatable? | ❌ (gas + Sybil risk) | ✅ role |

**On-chain badges** are minted as distinct, clearly-labeled honor NFTs (separate
from the collection; zero secondary-market framing). **Endorsements** are Discord
roles and, where a durable record helps, a **signed attestation** (the team
signs a message binding wallet → honor with a date) that the holder can show
without anything transferable.

---

## 3. Badge catalog & earn conditions

Tiers of honor, shallow → deep, mirroring the dive:

### Participation honors (roles, automatic-ish, low stakes)
- **Boarded** — verified holder of any minted NFT. Role, auto-granted on wallet
  verification.
- **Salvage Crew** — held through The Scuttling (did not sell before mint close).
  Role, granted from on-chain snapshot at close.
- **Depth ranks** (Snorkeler … Admiral) — cosmetic roles matching the deepest
  Dive Pass tier a wallet minted. Role, from mint records.

### Contribution honors (human-reviewed, medium stakes)
- **Lamp Keeper** — kept the community lit during a quiet stretch (sustained
  helpfulness, answering newcomers). Monthly, nominated + team-confirmed.
- **Shipwright's Mark** — shipped something for the crew: art, a tool, a guide, a
  translation, an event. Team-attested; may be an on-chain badge for major work.
- **Cartographer** — produced lasting reference material (docs, maps, explainers)
  the team adopts.

### Deep honors (rare, on-chain, historic)
- **First Divers** — early, materially-helpful members before launch. One-time,
  on-chain badge, capped and dated.
- **Last Men Aboard** — recognized for conviction through a genuinely hard
  period. One-time, on-chain, team-attested only.
- **Wizard of the Deep** — the apex earned honor. Tied to the OPS-3 puzzle;
  confers the earned Hadal pass + guaranteed grail. Never sold, never farmable
  (see the OPS-3 design proposal). Exactly as many as the puzzle yields.

Each badge entry, when operationalized, gets: a one-line meaning, explicit earn
condition, issuance channel (role vs NFT vs attestation), and a cap if any.

---

## 4. Anti-gaming

- **No pay-to-earn, ever.** Nothing on this list is unlocked by spending money.
- **Sybil resistance:** deep honors require human attestation and are capped;
  participation roles are tied to on-chain holdings (one honor per wallet, and
  snapshots dedupe obvious multi-wallet farming by weighting *contribution
  quality* over *account count*).
- **No public point leaderboards.** Points invite farming and financialization.
  Recognition is qualitative and issued in named honors, not a grindable score.
- **Contribution honors are nominated, not claimed.** A member nominates another;
  the team confirms. Self-nomination is allowed but weighted lower and always
  human-reviewed.
- **Cooldowns:** medium honors are issued on a monthly cadence, not on-demand,
  removing the incentive to spam activity right before a drop.
- **Revocation policy (off-chain honors):** roles can be removed for bad-faith
  behavior; the policy is published so it is predictable, not arbitrary. On-chain
  badges are not revoked (chosen only for honors that stay true forever).
- **No trait/mint advantage from badges** except the one designed exception, the
  Wizard's earned pass — and that runs through the same provably-fair engine.

---

## 5. Discord structure (minimal, low-ops)

**Channels (lean):**
- `#deck` — announcements (team-only posting).
- `#the-crew` — general.
- `#salvage-bay` — show your work / contributions (feeds Shipwright's Mark noms).
- `#lore` — depth drops + discussion.
- `#fairness` — verification help; pin the reveal/verify steps.
- `#depth-log` — bot posts honors as they're granted (transparency).
- `#nominations` — members nominate others for contribution honors.

**Roles (mirror the badges):** Boarded, Salvage Crew, depth ranks, Lamp Keeper,
Shipwright, Cartographer, First Diver, and the deep honors. Roles are visual
(colored, lore-named), not gated paywalls.

**Verification:** standard hold-to-verify bot mapping wallet → holder role. Keep
it to one bot to stay low-maintenance.

---

## 6. Six-month low-cost engagement calendar

Designed for a small team: one recurring ritual per week, one larger beat per
month, all cheap to run. "Depth drop" = a lore post from the series in the copy
kit.

| Month | Weekly ritual | Monthly beat | Honors issued |
|---|---|---|---|
| 1 | Depth drop (Surface→) | Fairness AMA (how commit–reveal works) | Boarded roles live |
| 2 | Salvage-bay spotlight | First community art challenge (no prize $) | First Shipwright's Marks |
| 3 | "Verify-along" (recompute a chest together) | Lore quiz night | Cartographer debuts |
| 4 | Depth drop continues | Grail-story reading (bios from P1) | Lamp Keeper (month 1 winners) |
| 5 | Newcomer welcome hour | Community build showcase | Shipwright's Marks (major work → on-chain) |
| 6 | Recap threads | Scuttling-anniversary / retrospective | Last Men Aboard (if earned) |

Guardrails for every event: no financial talk, no giveaways framed as returns,
Tom Bepe stays original, and any on-chain badge minting is announced with the
standing disclaimer.

---

## 7. Issuance process (operational checklist)

1. Nomination lands in `#nominations` (or team identifies a First/Last honor).
2. Team confirms the earn condition is genuinely met (human review for medium+).
3. Choose vehicle per §2 (role vs attestation vs on-chain badge).
4. If on-chain: mint a clearly-labeled honor NFT, log it in `#depth-log`, attach
   the disclaimer, never list it for sale.
5. Record the grant (wallet/handle, honor, date, reason) in a private ops sheet
   for continuity and cap-tracking.
6. Announce with lore voice; celebrate the person, not a price.
