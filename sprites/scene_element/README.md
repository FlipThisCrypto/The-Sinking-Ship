# sprites/scene_element — Scene Element

z-order: 3 | required: False | dimensions: 2048x2048 RGBA PNG (illustration profile)

> **PRODUCTION ART** — authored by `engine/artgen/scene_element.py`, regenerate
> with `python scripts/gen_art.py --layer scene_element`. Originals frozen in
> [`vault/sprites-v1/`](../../vault/README.md).

## Composition contract

Forty plates across five series — harbor, military, pirate, wizard, crystal.
The layer is single-select, so exactly one series appears per NFT and they never
mix by construction. Every element has to share a frame with any of the sixteen
ships, which drives two rules:

- **Everything reads as distance.** These sit *behind* the vessel (z-order 3),
  so they are drawn small, seated on the shared waterline (`SEA_HORIZON`, the
  same 0.58 the sea and ship_condition layers use), with thinner strokes and
  lower contrast than the ship's linework. An element that competes with the
  ship for weight stops being a setting and becomes clutter.
- **The centre is surrendered.** `clearance_mask` attenuates alpha inside the
  ellipse the ship's mass occupies, so structures pass *behind* the hull rather
  than tangling with it. The wizard and crystal series, meant to float around
  the vessel, carry a weaker clearance.

Elements spread along the horizon — convoys, fog fleets, reefs — necessarily
have some mass where the ship is, because they are at the same distance. The
clearance mask keeps it faint; measured, the densest core coverage is 0.033.

| file | trait |
|---|---|
| `harbor_abandoned_harbor.png` | Abandoned Harbor |
| `harbor_broken_pier.png` | Broken Pier |
| `harbor_storm_harbor.png` | Storm Harbor |
| `harbor_ship_graveyard.png` | Ship Graveyard |
| `harbor_dry_dock.png` | Dry Dock |
| `harbor_lighthouse.png` | Lighthouse |
| `harbor_military_port.png` | Military Port |
| `harbor_pirate_cove.png` | Pirate Cove |
| `harbor_wizard_harbor.png` | Wizard Harbor |
| `military_convoy_silhouettes.png` | Convoy Silhouettes |
| `military_artillery_smoke.png` | Artillery Smoke |
| `military_searchlights.png` | Searchlights |
| `military_signal_flags.png` | Signal Flags |
| `military_cargo_drop.png` | Cargo Drop |
| `military_helicopter.png` | Helicopter |
| `pirate_black_flag.png` | Black Flag |
| `pirate_fog_fleet.png` | Fog Fleet |
| `pirate_crows_nest.png` | Crow's Nest |
| `pirate_hidden_cove.png` | Hidden Cove |
| `pirate_treasure_island.png` | Treasure Island |
| `pirate_ghost_fleet.png` | Ghost Fleet |
| `pirate_skeleton_crew.png` | Skeleton Crew |
| `wizard_green_magic.png` | Green Magic |
| `wizard_purple_magic.png` | Purple Magic |
| `wizard_magic_lanterns.png` | Magic Lanterns |
| `wizard_spell_circle.png` | Spell Circle |
| `wizard_floating_runes.png` | Floating Runes |
| `wizard_summoning_circle.png` | Summoning Circle |
| `wizard_blockchain_sigils.png` | Blockchain Sigils |
| `wizard_offer_file_scroll.png` | Offer File Scroll |
| `crystal_emerald_horizon.png` | Emerald Horizon |
| `crystal_crystal_reef.png` | Crystal Reef |
| `crystal_crystal_moon.png` | Crystal Moon |
| `crystal_fractured.png` | Fractured |
| `crystal_black.png` | Black |
| `crystal_ruby.png` | Ruby |
| `crystal_sapphire.png` | Sapphire |
| `crystal_corrupted.png` | Corrupted |
| `crystal_void.png` | Void |
| `crystal_chia_crystal.png` | Chia Crystal |
