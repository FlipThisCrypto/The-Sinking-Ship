# TODO — P8: Chest-opening reveal web app

**Status:** static mock prototype shipped at `site/reveal.html`.
Not wired to live manifests or wallet yet.

## Shipped (demo)

- Underwater/chest UI with closed → open asset swap
- Loads real `demo_chest.json` (chest-manifest-v1 shape from shipgen)
- Sequential NFT surface cards with rarity-tiered labels/effects copy
- Share line: “I struck [rarity] at [depth]”
- Links to fairness page
- JS DRBG module + browser self-check on fairness page
  (`site/js/shipgen_drbg.js`, Node: `node site/js/verify_vectors.mjs`)

## Integration contract (unchanged)

- **Input:** chest manifest JSON after offer take confirms — never before.
- **Verification:** DRBG JS port + vectors; full roll port still open.
- **Art:** `render_engine.py` 2048px outputs.
- **Odds:** `tiers.js` / fairness page from config (single source of truth).

## Also shipped

- [x] Share-card generator: `scripts/gen_share_card.py`
- [x] Wallet onboarding page: `site/wallet.html` (static 60s guide)

## Remaining work

1. ~~Load real manifest by opaque offer id~~ — client supports `?offer=<id>` → `chests/<id>.json` and `?manifest=<rel.json>` (same-origin, path-safe). Host still must publish chest JSON next to the site.
2. Full JS roll-engine port (DRBG KAT already green).
3. Live WalletConnect pairing (page is guide-only).
4. Production CDN cache tiers + reveal-day cache flip.
