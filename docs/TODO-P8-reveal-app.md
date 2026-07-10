# TODO — P8: Chest-opening reveal web app (design brief)

**Status:** not built this session. This brief captures the integration
contract so P8 can be built without re-opening engine decisions.

## Experience (spec P8)

Underwater scene matching the buyer's tier zone (palette.json zone
sub-palettes are the color source of truth) → pixel-art chest on the seabed
→ chunky no-AA opening animation → NFTs surface one by one with
rarity-tiered effects:

| Rarity | Effect |
|---|---|
| common | bubbles |
| uncommon | bubble burst + glint |
| rare | light shaft |
| epic | zone-colored glow ring |
| legendary | full-screen shimmer |
| mythic | full-screen aura + palette flash |
| grail | bespoke sequence (one per grail set) |

Plus: 60-second Sage wallet + offer-acceptance onboarding (spec Risk 4),
tier odds table rendered from tiers.json + weights.json (transparency,
spec Risk 3), and a shareable "I struck [rarity] at [depth]" card.

## Integration contract (fixed by this session's engine)

- **Input:** chest manifest JSON (`chest-manifest-v1`) fetched from the
  fulfillment service by opaque offer id AFTER the take confirms — never
  before (blind mint).
- **Verification:** ship a JS re-implementation of `shipgen` (HMAC-SHA256
  DRBG + roll engine, both pure and documented in ADR-0002/0003) so holders
  can verify any chest in-browser post-reveal from (salt, coin_id). The
  golden vectors in `tests/test_drbg.py` and `tests/test_determinism.py`
  are the cross-language conformance suite.
- **Art:** `render_engine.py --render-manifest` outputs; reveal pulls
  2048px PNGs. Pre-reveal placeholder art must live on a short-cache path
  (reveal-day flip vs immutable image caching — reference-repo scar,
  ADR-0001 B6/B7).
- **Odds page data:** generate from tiers.json at build time; never
  hand-copy numbers (single source of truth).

## Patterns to carry from the reference (ADR-0001)

- Wallet module shape: one `wallet.js`, generic `requestRpc`, session
  restore, `wallet:change` event bus; **vendored** WalletConnect bundles
  (no CDN on a page that requests spends).
- Offer-download fallback for wallets without `chia_takeOffer` — the
  reference documented it but never shipped it; we ship it.
- `stats.json`-style pre-aggregated payload so the pre-reveal page never
  needs (and can never leak) the full manifest.
- Graceful anonymous degradation: wallet connection unlocks, never gates.

## Remaining work

1. React prototype with mock manifests (single-file artifact first).
2. JS shipgen port + conformance run against the Python golden vectors.
3. Share-card generator (server-side Pillow, reuse the reference's
   OG-image approach — but showcase tiers/odds, never "rarest pieces").
4. Production plan: hosting, CDN cache tiers per asset class, reveal-day
   cache-flip procedure.
