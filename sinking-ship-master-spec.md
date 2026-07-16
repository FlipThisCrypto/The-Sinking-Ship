# THE SINKING SHIP — Master Project Specification v1.0

**Chain:** Chia | **Supply cap:** 44,444 | **Format:** 48×48 master pixels, nearest-neighbor upscale to 2048×2048 and 4000×4000, no anti-aliasing | **Metadata:** CHIP-0007 | **Mint:** Blind mint via Secure the Mint + offer files

**Tagline:** *Hope never sinks.*

---

## 1. THE CONCEPT, SHARPENED

The original framing is strong but the mint mechanic and the lore were two separate ideas. This spec fuses them into one:

**The world sees a sinking ship. You see a salvage operation.**

The ship went down in the bear market. The tourists left. The press wrote the obituary. But the cargo — the memes, the tools, the culture, the builders — is still down there. The mint is not "buying a JPEG." The mint is **diving**. You buy dive gear. The deeper you can afford to go, the more treasure chests you can open, and the stranger and more valuable what you find becomes.

This makes every element cohere:

- **Mint passes = dive gear tiers** (snorkel → scuba → submarine → the abyss)
- **Mint experience = opening a treasure chest** recovered from the wreck
- **The NFTs = what the divers salvaged** — characters, ships, artifacts of a civilization that refused to die
- **Rarity = depth.** Common things float near the surface. Grails live in the Hadal zone.
- **The community = the Salvage Crew.** Everyone who minted dove when others walked away.

One-line pitch: *"Everyone abandoned ship. We went back down for the treasure."*

---

## 2. LORE STRUCTURE — THE FIVE DEPTHS

The lore is organized as five depth zones. These zones drive **everything**: mint tiers, rarity odds, background art, reveal chapters, and post-mint content. This is the spine of the project.

| Zone | Depth | Lore chapter | Emotional beat |
|---|---|---|---|
| 0. The Surface | 0m | *The Abandonment* — lifeboats, laughter, headlines | Despair |
| 1. Sunlight Zone | 0–200m | *The Doubters* — wreckage visible from above, "told you so" | Doubt |
| 2. Twilight Zone | 200–1,000m | *The Loyal* — first divers find lights still on below deck | Loyalty |
| 3. Midnight Zone | 1,000–4,000m | *The Crew* — builders found still working, memes still posting | Humor / Brotherhood |
| 4. Abyssal Zone | 4,000–6,000m | *The Forge* — the ship isn't sinking; it's being rebuilt underwater | Building |
| 5. Hadal Zone | 6,000m+ | *The Light Below* — the wizards, the source, hope itself | Hope |

Each zone gets a short lore drop (200–400 words + one hero pixel artwork) released weekly pre-mint. Six drops = six weeks of narrative marketing that doubles as worldbuilding.

**Tom Bepe** is the recurring figure: an original, Bepe-inspired (legally distinct — original design, no protected assets) amphibian everyman. He appears in every zone. On the surface he's crying in a lifeboat. In the Hadal zone he's welding the keel of a new ship by wizard-light. Same character, full emotional arc.

---

## 3. TRAIT SYSTEM — CLEANED, CONSOLIDATED, LAYERED

The original trait list had overlaps (Cigar appeared in both "Traits" and "Mouth"; smoking was a trait AND a mouth item; scene series overlapped with backgrounds). Below is the consolidated **9-layer stack**, rendered bottom-to-top.

### Layer stack (render order)

1. **Sky** (background top)
2. **Sea** (background bottom — sky+sea pairs are constrained, see rules)
3. **Scene Element** (harbor / crystal / military / pirate / wizard set-dressing — one series per NFT max)
4. **Ship Class**
5. **Ship Condition** (overlay: fire, flood line, tilt, ghost shader, etc.)
6. **Body** (Tom Bepe variant × pose, pre-composited sprites)
7. **Clothing**
8. **Eyes**
9. **Mouth** (item or none)
10. **Hat**
11. **Aura / Effect** (rare top layer: magic, crystal glow, halo light, laser bloom)

> Note: 11 conceptual layers, but Sky+Sea ship as paired "Environment" sprites at 48×48 to keep horizons clean, and Body×Pose is pre-composited. Effective generative layers: **9**.

### 3.1 Sky (14 traits)
Calm Blue, Orange Sunset, Golden Sunset, Moonlit, Overcast, Heavy Rain, Lightning, Purple Storm, Fog, Aurora, Green Aurora, Meteor Shower, Blood Moon, Solar Eclipse, Fire Sky

### 3.2 Sea (11 traits)
Calm, Storm Swell, Black Sea, Frozen, Emerald Water, Red Water, Abyss, Whirlpool, Glass Sea (mirror-still, eerie), Bioluminescent, Chia-Green Tide

### 3.3 Scene Element (5 series + None)
- **None** (majority of supply — keeps the composition clean)
- **Harbor series:** Abandoned Harbor, Storm Harbor, Military Port, Pirate Cove, Wizard Harbor, Lighthouse, Ship Graveyard, Dry Dock, Broken Pier
- **Military series:** Convoy Silhouettes, Artillery Smoke, Searchlights, Signal Flags, Cargo Drop, Helicopter (rare)
- **Pirate series:** Ghost Fleet, Black Flag, Fog Fleet, Treasure Island, Crow's Nest, Skeleton Crew, Hidden Cove
- **Wizard series:** Spell Circle, Floating Runes, Green Magic, Purple Magic, Magic Lanterns, Summoning Circle, Blockchain Sigils, Offer File Scroll
- **Crystal series:** Emerald Horizon, Crystal Reef, Crystal Moon, Fractured, Corrupted, Black, Ruby, Sapphire, Void, Chia Crystal

### 3.4 Ship Class (14 — trimmed from 18 for art budget sanity)
Raft, Lifeboat, Tug Boat, Fishing Boat, Cargo Ship, Steam Ship, Luxury Yacht, Cruiser, Battleship, Aircraft Carrier, Submarine, Pirate Ship, Ghost Ship, The Ark, Wizard Ship, Blockchain Ship
*(Cut: Destroyer folds into Battleship/Cruiser; Container folds into Cargo. If art budget allows, restore later as a "Fleet Expansion.")*

### 3.5 Ship Condition (9 — trimmed from 12)
Floating, Listing, Half Sunk, Flooded, Burning, Broken Mast, Split Hull, Fully Underwater, Ghost, **Rebuilt** (rare — scaffolding, welding sparks: the payoff condition), Being Salvaged

### 3.6 Body (8 variants × 6 poses = 48 pre-composited sprites)
**Variants:** Green, Blue, Zombie, Ghost, Gold, Emerald, Corrupted, Chrome
**Poses:** Standing, Saluting, Sitting, On Bow, Back Turned, Looking Down
*(Cut "Looking at Horizon" as a pose — it becomes an Eyes trait direction instead. 48 body sprites is the single biggest art line item; do not expand this.)*

### 3.7 Clothing (14)
Yellow Jacket, Rain Jacket, Life Vest, Hoodie, Farmer Overalls, Suit, Military Coat, Captain Jacket, Admiral Uniform, Pirate Coat, Wizard Robe, Hazmat, Scuba Suit, Deep Sea Suit

### 3.8 Eyes (15)
Normal, Sleepy, Determined, Scared, Crying, Closed, Hopeful, Looking to Horizon, Dead, Heart, Diamond, XCH, Pixel Stars, Wizard, Laser, Middle Finger Pupils

### 3.9 Mouth (10 + None)
None, Toothpick, Bubble Gum, Cigarette, Cigar, Pipe, Whistle, Flask, Rose, Radio, Kazoo (meme tier)

### 3.10 Hat (14 + None)
None, Beanie, Headband, Beret, Helmet, Pilot Cap, Captain Hat, Admiral Hat, Pirate Hat, Wizard Hat, Diver Helmet, Crown, Halo, Horns

### 3.11 Aura / Effect (rare layer, ~8% of supply gets one)
Green Magic Glow, Purple Magic Glow, Crystal Shimmer, Halo Light, Laser Bloom, Ghost Fade, Golden Radiance, Corruption Static, Chia Bloom

### Exclusion & pairing rules (the cohesion engine)

These rules are what make 44,444 outputs feel *designed* instead of random slop:

- **Diver Helmet** excludes ALL mouth items and all other hats. (Pairs beautifully with Scuba/Deep Sea Suit — weight the pairing up.)
- **Ghost body** forces Ghost Fade aura eligibility, biases toward Ghost Ship / Moonlit / Fog. Never pairs with Burning condition.
- **Fully Underwater** condition only pairs with Abyss, Bioluminescent, or Black Sea, and biases Scuba/Deep Sea clothing.
- **Submarine** excludes On Bow pose and Half Sunk/Listing conditions (subs don't list — they're either fine or gone).
- **Wizard Ship / Wizard Robe / Wizard Hat / Wizard eyes** cluster: any two wizard traits boost odds of a third (correlated rolls), so wizards feel like a faction, not a coincidence.
- **Halo excludes Horns** except on exactly **44 NFTs** where both appear ("The Torn" — instant sub-grail meme tier).
- **The Ark** only appears with Storm Swell, Heavy Rain, or Whirlpool.
- **Rebuilt** condition biases toward Builder-coded traits (overalls, determined eyes, toothpick) — the visual embodiment of the thesis.
- **Blood Moon + Ghost Ship + Skeleton Crew** allowed together only in Mythic rolls.
- Scene Element series never mixes (one series per NFT).

---

## 4. RARITY ARCHITECTURE

### 4.1 Rarity tiers (sum = 44,444 exactly)

| Tier | Count | % of supply | Definition |
|---|---|---|---|
| **Grail** (1/1) | 44 | 0.099% | Fully hand-crafted, override the generator entirely. Named. Lore-canon characters. |
| **Mythic** | 400 | 0.90% | Contains ≥1 Mythic-bucket trait + forced aura |
| **Legendary** | 1,500 | 3.38% | Contains ≥1 Legendary-bucket trait |
| **Epic** | 3,500 | 7.88% | Contains ≥1 Epic-bucket trait |
| **Rare** | 8,000 | 18.00% | Contains ≥1 Rare-bucket trait |
| **Uncommon** | 12,000 | 27.00% | — |
| **Common** | 19,000 | 42.75% | — |

44 grails in a 44,444 supply is clean symbolism — market it.

### 4.2 Weight framework

Assign every trait to a bucket; the generator uses bucket weights, then per-trait fine-tuning:

| Bucket | Base weight | Example traits |
|---|---|---|
| Common | 100 | Calm sky, Green body, Normal eyes, Hoodie, Fishing Boat, Floating |
| Uncommon | 40 | Orange Sunset, Blue body, Beanie, Cargo Ship, Listing, Toothpick |
| Rare | 15 | Aurora, Zombie body, Pirate Coat, Battleship, Burning, Laser eyes |
| Epic | 5 | Blood Moon, Ghost body, Wizard Robe, Ghost Ship, Split Hull, Halo |
| Legendary | 1.5 | Solar Eclipse, Gold body, The Ark, Rebuilt, Crown, XCH eyes |
| Mythic | 0.4 | Chrome body, Blockchain Ship, Chia Crystal scene, Corruption Static aura |

Full per-trait weight table is generated in **Prompt P3** (prompt pack) as a JSON config the rendering engine consumes — same pattern as the Empty Throne Pillow pipeline, so the sprite renderer is reusable.

### 4.3 The 44 Grails (hand-made 1/1s)

Themed sets of 4 across 11 concepts, e.g.: The Four Admirals, The Four Wizards of the Deep, The Four Horsemen of the Bear, The Lighthouse Keepers, The First Divers, The Last Men Aboard, The Shipwrights, The Ghost Captains, The Torn (halo+horns canon versions), The Salvage Kings, The Ark Builders. Each has a name, 2–3 sentence lore, and a guaranteed placement (see mint tiers — some grails are seeded into deep-tier chests, some auctioned).

---

## 5. MINT PASSES — THE DIVE GEAR SYSTEM

### 5.1 The mechanic

- Buyer purchases a **Dive Pass** (the mint pass) at a fixed XCH price.
- Each pass = one **treasure chest** containing a **randomized number of NFTs within the tier's range**. The randomness of quantity is part of the thrill — the chest might be light or heavy.
- Deeper tiers get: (a) more NFTs per XCH, (b) wider upside on quantity, (c) **Depth Luck** — multiplied odds on Epic+ rolls, and (d) **pity guarantees** (minimum rarity floors).
- Fulfilled via **Secure the Mint + offer files**: payment triggers creation of an offer file containing the tier's rolled NFTs; buyer accepts the offer; chest "opens" (reveal).

### 5.2 Tier table

| # | Tier | Zone | Price (XCH) | Chest range | E[mints] | Eff. price/NFT | Passes | E[supply used] | Depth Luck | Guarantee |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Castaway | Surface | 0.10 | 1 | 1 | 0.100 | 4,444 | 4,444 | 1.0× | — |
| 2 | Snorkeler | Sunlight | 0.25 | 2–4 | 3 | 0.083 | 2,920 | 8,760 | 1.0× | — |
| 3 | Scuba Diver | Sunlight | 0.40 | 4–6 | 5 | 0.080 | 1,600 | 8,000 | 1.1× | — |
| 4 | Deep Sea Diver | Twilight | 0.75 | 8–12 | 10 | 0.075 | 700 | 7,000 | 1.25× | ≥1 Rare |
| 5 | Salvage Crew | Twilight | 1.10 | 13–17 | 15 | 0.073 | 300 | 4,500 | 1.4× | ≥1 Rare |
| 6 | Submarine Captain | Midnight | 1.80 | 22–28 | 25 | 0.072 | 160 | 4,000 | 1.6× | ≥1 Epic |
| 7 | Shipwright | Abyssal | 3.50 | 45–55 | 50 | 0.070 | 70 | 3,500 | 2.0× | ≥2 Epic |
| 8 | Harbormaster | Abyssal | 5.50 | 90–110 | 100 | 0.055 | 25 | 2,500 | 2.5× | ≥1 Legendary |
| 9 | Admiral | Hadal | 10.00 | 230–270 | 250 | 0.040 | 5 | 1,250 | 3.0× | ≥1 Legendary + Grail lottery ticket |
| 10 | Wizard of the Deep | Hadal | Not for sale | 44 + 1 Grail | 45 | — | 1 | 45 | 10.0× | Guaranteed named Grail |

- **Treasury reserve:** 444 NFTs (team, collabs, contests). Symbolic number, disclose it publicly.
- **Expected supply if fully sold:** ~43,999 public mint + 444 reserve ≈ 44,443 (within the 44,444 cap; public mint budget 44,000). Variance absorbed by The Scuttling (below) and a hard budget check at fulfillment.
- **Full sellout revenue:** ~3,390 XCH. Model 25% / 50% / 75% sellout scenarios before committing to any spend.
- **Pricing revision (2026-07-11):** deep-tier prices raised so effective cost/NFT descends in a clean monotonic regression (0.100 → 0.040 across the sold tiers): Shipwright 3.20→3.50 (0.070/NFT), Harbormaster 4.40→5.50 (0.055/NFT), Admiral 5.00→10.00 (0.040/NFT).
- **Supply revision OQ-1 (2026-07-14, option B):** Snorkeler passes 3,000 → 2,920 (−80 × E[3] = −240 expected NFTs) so full-sellout expected consumption 43,999 ≤ public mint budget 44,000. Full-sellout revenue 3,409.90 → 3,389.90 XCH.
- **Wizard of the Deep** is earned, not bought — awarded via a lore puzzle / community quest during mint. This is the marketing centerpiece. Depth Luck for this tier is **10.0×** (finite; OQ-2 2026-07-14) so the 44-piece chest stays mixed salvage — disclose 10× on odds pages, not "infinite."
- **Admiral grail lottery:** 5 of the 44 grails are seeded randomly into the 5 Admiral chests. **11** are auctioned post-mint (OQ-4 2026-07-14: one auction slot funds the Wizard guaranteed grail). 27 are seeded into random chests across tiers 4–8 (published odds), so even a Deep Sea Diver can strike a grail — the "anyone can find treasure" hook.

### 5.3 The Scuttling (critical bear-market mechanism)

**Honest assessment: 44,444 is a very large supply for the current Chia NFT market.** Rather than shrink the symbolic number, make undersell a *feature*:

> When the mint window closes, all unminted supply is permanently destroyed — publicly, on-chain, with ceremony. **"Ships that never sailed are scuttled."**

- Final supply = exactly what the divers salvaged. Every undersold pass makes every held NFT scarcer.
- Kills the overhang that haunts big collections in bear markets ("when does the rest dump?").
- Perfect lore fit: the ocean keeps what nobody came back for.
- Converts the biggest risk (undersell) into the strongest holder incentive (scarcity event + FOMO in the final 48 hours).
- Mechanically: since generation happens at chest-open time, "scuttling" = publishing the final minted count, retiring the generator seed, and burning the reserve overflow. Announce the exact procedure pre-mint.

### 5.4 Fairness / blind mint integrity (this is where Chia-native credibility is won)

1. **Provenance commitment:** Before mint opens, publish SHA-256 hash of (full trait config JSON + weights + grail placements + RNG algorithm + secret salt).
2. **Chest rolls:** quantity roll + trait rolls seeded by `HMAC(secret_salt, payment_coin_id)` — deterministic, per-purchase, unmanipulable after the commitment, and tied to an on-chain identifier the buyer can verify.
3. **Post-mint reveal:** publish the salt + full config. Anyone can recompute every chest and verify nothing was rigged. 
4. Mint from a project **DID**, royalty set on-chain (recommend 5%), CHIP-0007 metadata with the collection provenance hash in `attributes`.

This turns "blind mint" from a trust-me into a verifiable commit-reveal — a genuine differentiator worth a dedicated docs page.

---

## 6. COMMUNITY TRAITS → HONOR SYSTEM (not random traits)

Tang Gang, Builder, Diamond Hands, Still Here, Never Jumped, Last Man Aboard, Meme Lord, Salvage Crew, Shipwright — these should **not** be random generative traits. Randomly assigning "Diamond Hands" to a flipper is hollow. Instead:

- Ship them as **soulbound-style badge NFTs / metadata endorsements earned by behavior**: held through reveal (Never Jumped), held 6 months (Diamond Hands), active pre-mint community member (Still Here), minted in the final scuttle hour (Last Man Aboard), won meme contests (Meme Lord), Tang Gang verified members (Tang Gang).
- Post-mint, badges can gate salvage events, allowlists for the Fleet Expansion, and $-token or reward mechanics if you later bridge to your existing reward-puzzle architecture.

This converts a static trait list into a **retention engine**, which is what a bear-market project actually needs.

---

## 7. ART PRODUCTION BUDGET (sprite count reality check)

| Layer | Sprites |
|---|---|
| Sky | 15 |
| Sea | 11 |
| Scene Elements | ~40 |
| Ships | 16 |
| Conditions (overlays; some ship-specific variants) | ~30 |
| Body × Pose | 48 |
| Clothing (× pose adaptation where needed) | ~30 |
| Eyes | 16 |
| Mouth | 11 |
| Hats | 14 |
| Auras | 9 |
| Grails (hand-made) | 44 |
| Lore hero art | 6 |
| Chest/reveal art + site assets | ~15 |
| **Total** | **~305 sprites** |

At 48×48 this is very achievable solo/small-team, especially reusing the Empty Throne Pillow rendering engine (layer compositing, alpha binarization, palette snapping, nearest-neighbor upscale all carry over directly).

**Palette discipline:** define one 32-color master palette + 6 zone-specific 12-color sub-palettes (one per depth zone). Every sprite snaps to the master palette; backgrounds snap to their zone sub-palette. This is what makes 44k outputs look like one world.

---

## 8. ROADMAP

**Phase 0 — Foundation (weeks 1–3):** finalize this spec, trait JSON, weight config; adapt rendering engine; produce palette + 20 proof sprites; generate 500 test outputs and eyeball cohesion; iterate exclusion rules.

**Phase 1 — The Six Drops (weeks 4–9):** weekly depth-zone lore drops; open "Dive Manifest" (allowlist); Wizard of the Deep puzzle begins; publish provenance hash + fairness docs.

**Phase 2 — The Dive (mint, 2–3 weeks):** tiered mint opens all-at-once (scarcity of deep passes creates natural urgency); live chest-opening reveals; grail strikes celebrated publicly; final 48h Scuttling countdown.

**Phase 3 — The Scuttling:** on-chain burn ceremony; final supply announced; salt revealed; verification tools published.

**Phase 4 — The Salvage Era (post-mint):** honor badges distributed; grail auctions (the 12); meme contests; optional Fleet Expansion or reward-token mechanics only if the market supports it. Do not promise a roadmap you can't fund at 25% sellout.

---

## 9. RISKS & HONEST NOTES

1. **Supply size.** 44,444 on Chia today is aggressive. The Scuttling makes it survivable, but budget and messaging must assume partial sellout is the base case, not the failure case.
2. **Pepe-derivative IP.** "Bepe-inspired" needs to be an original design. No traced silhouettes, no protected marks, distinct proportions/features. Same discipline as the "FF7 mood without FF7 assets" rule — moods and genres aren't protectable; specific expressions are.
3. **Randomized quantity + rarity boosts = gacha optics.** Publish exact odds for every tier (ranges, luck multipliers, guarantees, grail seeding). Full transparency is both ethically right and your best marketing asset.
4. **Offer-file UX.** Offer acceptance is a friction point for newcomers — the chest-opening web experience must hand-hold wallet setup (Sage) with a 60-second guide.
5. **Ops load.** Automated offer generation must be rock solid (Sage RPC, mTLS, 127.0.0.1:9257 pattern you've already validated). Load-test the fulfillment path before mint day.
