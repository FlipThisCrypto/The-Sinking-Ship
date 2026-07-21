# THE SINKING SHIP — Launch Copy Kit (P10)

> One place for every piece of launch copy: one-pager, threads, mint-day
> sequence, tier lines, teasers, captions, and the compliance guardrails that
> apply to all of it. Voice is defined in
> [`docs/lore/LORE-BIBLE.md`](../lore/LORE-BIBLE.md); marketplace-specific
> blurbs live in [`MARKETPLACE-COPY.md`](MARKETPLACE-COPY.md).

**Status:** complete first edition (P10). All numbers below are drawn from
`config/tiers.json` and the master spec — if a config value changes, update the
figures here in the same PR.

---

## 0. Voice & compliance guardrails (read first)

**Voice:** heavy, hopeful, meme-literate. Conviction, not cope. Never celebrate
failure; celebrate the people who stayed to build.

**Hard rules — never break, in any channel:**

- **No financial claims.** No price predictions, no "floor," no "returns," no
  "investment," no "guaranteed" anything of monetary value. Art and community,
  not a security.
- **No profit framing.** The value proposition is salvage, craft, and
  conviction — not money made.
- **No pre-reveal trait leaks.** Never imply a buyer can see what a chest holds
  before payment settles. That would break the fairness scheme.
- **No fake scarcity or fake urgency.** The Scuttling is real and on-chain; do
  not invent countdowns or "last chance" pressure beyond the true mint window.
- **Tom Bepe is an original character.** Legally distinct amphibian everyman —
  never "Pepe," never Pepe IP or imagery.
- **Testnet before mainnet, always.** Never announce a mainnet mint before the
  testnet11 go/no-go is green.

**Standing disclaimer (append to any post that could be read as promotional):**

> Art collectible on Chia. Not an investment, not financial advice. Supply that
> is not minted is destroyed at close (The Scuttling). Verify every roll
> yourself after reveal.

---

## 1. One-pager

**THE SINKING SHIP — *Hope never sinks.***

*Everyone abandoned ship. We went back down for the treasure.*

- **What:** a 44,444-supply, hand-drawn (Amano-style ink) NFT collection on the
  **Chia** blockchain.
- **How you mint:** you buy a **Dive Pass** — the depth of your gear is the depth
  of your salvage. Each pass opens a **treasure chest** of randomized NFTs with
  **published odds**, a **Depth Luck** multiplier that rises with tier, and
  built-in rarity **guarantees** at deeper tiers.
- **Why you can trust it:** a **commit–reveal** fairness scheme. Before mint we
  publish one commitment hash over the rules, odds, and a secret salt. Your
  payment coin id seeds your chest — not a server roll. After mint we reveal the
  salt and anyone can recompute every chest.
- **The Scuttling:** when the window closes, unminted supply is **permanently
  destroyed on-chain**. Final supply is only what divers salvaged.
- **The grails:** 44 hand-crafted 1/1s seeded into the deep — some by lottery,
  some reserved for a post-mint auction, one earned by the Wizard of the Deep.
- **The thesis:** builders create value after everyone leaves. This is a salvage
  operation, not a lifeboat.

Links: landing · fairness (provably fair) · reveal demo · wallet onboarding.

---

## 2. Social bios

- **≤160 chars:** Salvage ops on Chia. 44,444. Blind mint. Provably fair. Hope
  never sinks.
- **≤80 chars:** THE SINKING SHIP · 44,444 on Chia · provably fair salvage.
- **Handle tagline:** *Hope never sinks.*

---

## 3. Lore-drop thread series (one per depth)

Post cadence: one depth per drop, surface → hadal, in the run-up to mint. Each
opens with the zone name and its emotion, closes with the tagline. No mint
mechanics in lore drops — those live in the fairness/mint posts.

1. **The Surface — *The Abandonment* (Despair).** The ship was built for bull
   markets: hull plated with slogans, sails stitched from screenshots of
   all-time highs. When the weather turned, the tourists photographed the list
   of the deck and left in ordered lifeboats. The press wrote the obituary
   before the last light went out. *Hope never sinks.*
2. **Sunlight Zone — *The Doubters* (Doubt).** Wreckage you can still see from
   above. "Told you so" travels at light speed; conviction has to swim. The
   first fins in the water look foolish — until they find a hatch that still
   opens. *Hope never sinks.*
3. **Twilight Zone — *The Loyal* (Loyalty).** The lights are still on below
   deck. Someone kept the boiler fed. Loyalty isn't loud; it's a lamp that
   should have gone out and didn't. *Hope never sinks.*
4. **Midnight Zone — *The Crew* (Brotherhood).** Builders found still working. A
   thousand meters of no sunlight and the jokes still land. Brotherhood is a
   pressure hull. *Hope never sinks.*
5. **Abyssal Zone — *The Forge* (Building).** The ship isn't sinking — it's being
   rebuilt underwater. Sparks look like stars when it's dark enough.
   Scaffolding on a keel is a love letter to the future. *Hope never sinks.*
6. **Hadal Zone — *The Light Below* (Hope).** At the bottom of everything there
   is a light, and it is not the sun. The wizards. The source. The reason we
   dove. *Hope never sinks.*

---

## 4. Mint-day post sequence

**T-minus (pre-mint, commitment published):**
> The rules are locked. We just published the commitment hash — every trait,
> weight, and odd, sealed before a single pass is sold. When the salt is
> revealed after mint, you can recompute every chest yourself. This is what
> "provably fair" means. Dive when you're ready.

**Go-live:**
> The dive is open. Pick your Dive Pass — the deeper your gear, the deeper your
> salvage — and open your chest. Odds are published. The salt is committed.
> Nothing about your roll can change after you pay. *Hope never sinks.*

**Mid-window (reassurance, not hype):**
> No countdown theater. The window is the window; unminted ships are scuttled at
> close. If you're here, you're here because the cargo is worth going down for —
> not because someone told you to hurry.

**The Scuttling (at close):**
> Mint is closed. Every unminted ship is now being destroyed on-chain — publicly,
> with ceremony. Final supply equals what the salvage crew brought up. Ships that
> never sailed are scuttled. What you hold is what was saved.

**Post-mint (reveal + verify):**
> The salt is revealed. Take any chest manifest and run the verifier — the roll
> reproduces bit-for-bit or it doesn't. Ours does. Welcome to the crew.

---

## 5. Dive Pass tier lines

Ten tiers, surface to hadal. Prices in XCH from `config/tiers.json`; the Wizard
of the Deep pass is **earned, never sold**.

| Tier | Zone | Price | Chest size | Depth Luck | One-liner |
|---|---|---|---|---|---|
| Castaway | surface | 0.10 | 1 | 1.0× | First step off the lifeboat. |
| Snorkeler | sunlight | 0.25 | 2–4 | 1.0× | Toes in the wreck-light. |
| Scuba Diver | sunlight | 0.40 | 4–6 | 1.1× | Gear on, doubt off. |
| Deep Sea Diver | twilight | 0.75 | 8–12 | 1.25× | Past where the tourists watched. Guarantees a Rare. |
| Salvage Crew | twilight | 1.10 | 13–17 | 1.4× | You came to work. Guarantees a Rare. |
| Submarine Captain | midnight | 1.80 | 22–28 | 1.6× | Command below the light. Guarantees an Epic. |
| Shipwright | abyssal | 3.50 | 45–55 | 2.0× | You don't salvage the ship — you rebuild it. Guarantees 2 Epics. |
| Harbormaster | abyssal | 5.50 | 90–110 | 2.5× | You run the depth now. Guarantees a Legendary. |
| Admiral | hadal | 10.00 | 230–270 | 3.0× | The deepest gear. A Legendary floor and a shot at a seeded grail. |
| Wizard of the Deep | hadal | earned | 44 | 10.0× | Not for sale. The light below, and a grail of your own. |

Compliance note: "guarantees a Rare/Epic/Legendary" refers to **rarity tier
inside the chest** (a published mechanic), never to monetary value.

---

## 6. Wizard of the Deep teaser

> There is a pass no store will ever sell you. It isn't minted with coin — it's
> earned in the dark. The Wizard of the Deep carries the deepest luck in the
> collection and a grail that belongs to no one else. How you earn it is part of
> the descent. Keep diving.

Do **not** reveal the puzzle mechanics in marketing (see the OPS-3 design
proposal). Tease the existence and the stakes, never the solution.

---

## 7. Evergreen captions

- Everyone abandoned ship. We went back down for the treasure.
- The world sees a sinking ship. You see a salvage operation.
- Conviction has to swim.
- Brotherhood is a pressure hull.
- Ships that never sailed are scuttled.
- At the bottom of everything there is a light, and it is not the sun.
- We didn't come to mourn. We came with dive gear.
- Hope never sinks.

---

## 8. FAQ snippets (reusable answers)

- **Is this an investment?** No. It's an art collectible on Chia. No returns, no
  promises — just the work of going back down.
- **How is it fair?** Commit–reveal. We publish a hash before mint; your payment
  coin seeds your chest; we reveal the salt after and you recompute every roll
  yourself.
- **What is The Scuttling?** At mint close, all unminted supply is destroyed
  on-chain. Final supply is only what was salvaged.
- **Can I see my chest before I pay?** No — and that's the point. Traits are
  never revealed before payment settles.
- **What chain / wallet?** Chia, via offer files. Sage wallet; see the wallet
  onboarding page.
- **How many grails?** 44 hand-crafted 1/1s, seeded across the deep.

---

## 9. Do-not-say list (compliance quick reference)

Never publish: "floor price," "guaranteed profit/returns," "to the moon,"
"can't lose," "next 100x," "financial advice," "presale allocation guarantees
value," "Pepe," any implied ability to see traits pre-payment, or any mainnet
date before testnet go/no-go is green.
