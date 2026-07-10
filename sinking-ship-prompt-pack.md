# THE SINKING SHIP — Fable 5 Prompt Pack

How to use: start a fresh chat per prompt, **attach `sinking-ship-master-spec.md` every time**, then paste the prompt. Run them roughly in order — later prompts consume outputs of earlier ones. Where a prompt says [ATTACH], attach the named file from the earlier step.

---

## P1 — Lore Bible

> Attached is the master spec for The Sinking Ship, a 44,444-supply pixel art NFT collection on Chia. Write the complete Lore Bible: (1) a 500-word origin myth of the ship and its abandonment, written in a darkwave/naval-mythology voice — sparse, heavy, memorable; (2) the six depth-zone lore drops per Section 2, each 250–350 words ending on a hook; (3) names and 2–3 sentence bios for all 44 Grails organized as 11 themed sets of 4 (Section 4.3); (4) the character sheet for Tom Bepe — personality, visual description (original design, Pepe-inspired but legally distinct), and his appearance in each zone; (5) a glossary of 20 in-world terms (The Scuttling, Dive Manifest, Depth Luck, etc.). Tone: FF7-era JRPG melancholy meets naval propaganda poster meets crypto meme culture. Never celebrate failure — the thesis is builders create value after everyone leaves. Output as a single markdown file.

## P2 — Trait Matrix JSON

> Attached is the master spec. Produce `traits.json`: a machine-readable trait matrix implementing Section 3 exactly. Schema: layers array (name, z_order, required boolean), each layer containing traits array (name, sprite_filename using snake_case, rarity_bucket from Section 4.2, notes). Include a top-level `exclusions` array and `pairings` array encoding every rule in Section 3's exclusion/pairing list as structured constraints: `{type: "exclude"|"require"|"bias", if: {layer, trait}, then: {layer, traits[], weight_multiplier?}}`. Also include the special "The Torn" rule (exactly 44 NFTs with Halo+Horns) as a `quota` constraint type. Validate that filename conventions are consistent and every trait in the spec appears exactly once. Output the complete JSON in an artifact.

## P3 — Rarity Weight Config

> Attached: master spec + [ATTACH traits.json from P2]. Produce `weights.json` assigning a numeric weight to every trait using the bucket base weights in Section 4.2, then fine-tune so that a 44,444-run Monte Carlo lands within ±5% of the rarity tier counts in Section 4.1 (19,000 Common / 12,000 Uncommon / 8,000 Rare / 3,500 Epic / 1,500 Legendary / 400 Mythic; the 44 Grails are excluded from generation). Include the Depth Luck multiplier table from Section 5.2 as `depth_luck` and the pity guarantees as `guarantees`. Then write `simulate.py` (Python, stdlib + numpy only) that loads traits.json + weights.json, applies all exclusion/pairing/quota constraints, simulates 44,444 mints, and prints the achieved rarity distribution and per-trait counts. Iterate the weights in your analysis until the simulation hits target. Deliver both files.

## P4 — Generative Rendering Engine

> Attached: master spec + traits.json + weights.json. Write `render_engine.py`, a Pillow-based pixel art compositor for 48×48 masters: loads layer sprites from `sprites/<layer>/<trait>.png`, composites in z-order per traits.json, enforces alpha binarization (no partial alpha), snaps output to a provided 32-color master palette (`palette.json`, also generate a sensible default with 6 depth-zone sub-palettes per Section 7), and exports 48×48 master + nearest-neighbor upscales at 2048×2048 and 4000×4000 with zero anti-aliasing. Include a `--validate-sprites` mode that scans the sprite directory for missing files, wrong dimensions, stray semi-transparent pixels, and off-palette colors. Structure it to reuse the cleanup patterns from my Empty Throne pipeline (alpha binarization, stray pixel removal, palette snapping). CLI with argparse, clear logging, no external services.

## P5 — Deterministic Chest Roller (fairness core)

> Attached: master spec + traits.json + weights.json. Implement `chest_roller.py` per Section 5.4: (1) `commit` command — takes config files + a secret salt, outputs the SHA-256 provenance commitment to publish pre-mint; (2) `roll` command — takes a tier name and a payment coin_id, derives seed = HMAC-SHA256(salt, coin_id), rolls chest quantity within the tier range, then rolls each NFT's traits applying weights, Depth Luck multipliers, pity guarantees, exclusion/pairing/quota constraints, and grail-seeding odds from Section 5.2; outputs a deterministic manifest JSON per chest; (3) `verify` command — given the revealed salt and any coin_id, recomputes and confirms a published chest. Determinism is non-negotiable: same inputs must always produce identical output across runs and machines (no unordered dict iteration, fixed numpy/random seeding, versioned config hash embedded in every manifest). Include unit tests proving determinism and guarantee enforcement.

## P6 — CHIP-0007 Metadata Generator

> Attached: master spec + a sample chest manifest from P5. Write `metadata_gen.py` producing CHIP-0007-compliant JSON for each NFT: name format "Sinking Ship #NNNNN", description drawn from a zone-appropriate line pool (generate 30 lines), attributes array from the trait manifest plus `rarity_tier`, `depth_zone`, and `provenance_hash`, collection block with the standard CHIP-0007 collection attributes (id, name, description, icon, banner, twitter, website, royalty info fields as used by Chia marketplaces). Include license field, and a `--batch` mode that processes a full mint run and validates every file against the CHIP-0007 schema. Flag anything ambiguous in the spec rather than guessing.

## P7 — Offer File Fulfillment Service (Sage RPC)

> Attached: master spec. Design and implement the fulfillment daemon per Sections 5.1/5.4 and Risk 5: a local Python service that (1) watches for confirmed tier payments (integrating with Secure the Mint's flow — leave the payment-detection interface abstract with a clean adapter class since STM's API is external), (2) calls chest_roller for the paying coin_id, (3) mints/assigns the rolled NFTs from the project DID, (4) constructs an offer file for those NFTs against 0 XCH (claim-style) or embeds fulfillment per STM's model — implement both strategies behind a flag, (5) delivers the offer file to the buyer, (6) logs everything to an append-only audit log with the manifest hash. Use Sage wallet's local RPC (HTTPS 127.0.0.1:9257, mTLS client certs) for all wallet operations. Include retry/idempotency (a payment must never be fulfilled twice), a dry-run mode against testnet, and a load-test script simulating 200 concurrent purchases. Ask me clarifying questions about the STM integration surface before writing code if needed.

## P8 — Chest-Opening Reveal Web App

> Attached: master spec. Build the mint-reveal web experience as a single-file React artifact first (prototype), then a production plan. The experience: user lands on an underwater scene matching their tier's depth zone (Section 2 palette moods), a pixel-art treasure chest sits on the seabed, opening animation (chunky pixel style, no anti-aliasing aesthetic), then their NFTs surface one by one with rarity-tier reveal effects (Common = bubbles, up through Mythic = full-screen aura, Grail = bespoke sequence). Include the 60-second Sage wallet + offer-acceptance onboarding flow from Risk 4, tier display with published odds (transparency requirement from Risk 3), and a shareable "I struck [rarity] at [depth]" card generator. Prototype with mock data; document the real integration points (fulfillment service webhook, offer file download).

## P9 — Fairness & Transparency Docs Page

> Attached: master spec + chest_roller.py from P5. Write the public "Provably Fair" documentation page: explain the commit-reveal scheme in plain language for non-technical buyers (analogy-driven), then a technical section with the exact hash construction, seed derivation, and step-by-step verification instructions using the `verify` command, then a full odds disclosure table (every tier: price, chest range, per-rarity odds after Depth Luck, guarantees, grail seeding odds). Include The Scuttling procedure spec (Section 5.3) as a public commitment. Tone: confident, precise, zero hype. This page is a trust document, not marketing.

## P10 — Marketing & Launch Copy Kit

> Attached: master spec + Lore Bible from P1. Produce the launch copy kit: (1) collection one-pager; (2) the six weekly lore-drop announcement posts (X/Twitter thread format, each 4–6 posts); (3) mint-day announcement + final-48-hours Scuttling countdown posts; (4) Dive Manifest allowlist announcement; (5) Wizard of the Deep puzzle teaser (don't reveal the puzzle — I'll design that separately); (6) 10 evergreen meme captions in the project voice; (7) marketplace collection description (short + long). Voice per the Lore Bible: heavy, hopeful, meme-literate, never desperate. Bear-market aware: the pitch is conviction, not promises of profit — no financial claims anywhere.

## P11 — Community & Honor Badge System Design

> Attached: master spec, Section 6. Design the full honor badge system: badge list with earn conditions and verification method for each (on-chain holdings checks vs. community verification), anti-gaming considerations, whether each badge is an NFT airdrop or metadata endorsement (recommend per badge with rationale for the Chia context), the Discord/community structure that supports it (channels, roles mapped to dive tiers and badges), and a 6-month post-mint engagement calendar of salvage events and meme contests that costs near-zero to run at 25% sellout revenue. Flag anything that creates unsustainable obligations.

## P12 — Master Test Plan & Launch Checklist

> Attached: master spec + all prior deliverables you have access to. Produce the pre-launch test plan and go/no-go checklist: sprite validation pass, 44,444-output cohesion review protocol (sampling method), determinism verification across machines, testnet end-to-end dry run (payment → roll → mint → offer → accept → reveal), provenance commitment publication steps, fulfillment load test acceptance criteria, incident runbook for mint-day failures (RPC down, double-fulfillment attempt, reveal site down), and The Scuttling execution procedure. Format as a checklist document I can literally work through.

---

### Suggested build order

P2 → P3 → P4 (art pipeline can start rendering tests) → P5 → P6 → P7 (technical core) → P1 → P10 → P9 → P11 (content) → P8 → P12 (launch).
