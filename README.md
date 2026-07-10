# THE SINKING SHIP

> *Hope never sinks.*

A 44,444-supply hand-drawn NFT collection on the **Chia blockchain**, in a
Yoshitaka Amano-style ink-illustration idiom (see
[docs/art-reference/ART-DIRECTION.md](docs/art-reference/ART-DIRECTION.md) and
[ADR-0008](docs/adr/ADR-0008-art-medium-full-amano-illustration.md) — the owner
chose illustration over the spec's original 48×48 pixel format; the render
engine supports both profiles). Blind mint via Secure the Mint + offer files,
with a verifiable commit–reveal fairness scheme.

**The world sees a sinking ship. You see a salvage operation.**

## Authoritative documents

| Document | Purpose |
|---|---|
| [sinking-ship-master-spec.md](sinking-ship-master-spec.md) | The full project specification. **Source of truth** — if code and spec disagree, the spec wins. |
| [sinking-ship-prompt-pack.md](sinking-ship-prompt-pack.md) | The build breakdown (P1–P12). |
| [docs/adr/](docs/adr/) | Architecture Decision Records for every significant technical decision. |

## Repository layout

```
config/        traits.json, weights.json, palette.json, tiers.json (+ JSON Schemas)
engine/        render_engine.py, chest_roller.py, metadata_gen.py, simulate.py
engine/shipgen shared library (config loading, deterministic RNG, roll core)
sprites/       one directory per layer; README per layer lists required files
tests/         pytest suite (determinism is the highest-priority property)
scripts/       helper CLIs (placeholder sprites, weight tuning, pipeline runner)
site/          static landing page (self-contained, no external deps)
docs/          ADRs + P7/P8 TODO design docs
output/        gitignored render/metadata/manifest output
```

## Quick start

```bash
pip install -r requirements.txt

# 1. Validate all configs against their schemas
python engine/validate_configs.py

# 2. Monte Carlo the rarity distribution (target: ±5% of spec Section 4.1;
#    use replicates — the mythic tier has ~5% single-run Poisson noise)
python engine/simulate.py --profile sellout --seed check --replicates 5 --check

# 3. Generate placeholder sprites for the active render profile and validate
#    (illustration by default per config/render.json; --profile pixel also works)
python scripts/gen_placeholder_sprites.py
python engine/render_engine.py --validate-sprites

# 4. Render sample outputs
python engine/render_engine.py --sample 25 --seed sample-run --outdir output/samples

# 5. Roll a test chest deterministically and verify it
python engine/chest_roller.py commit --salt-file test.salt
python engine/chest_roller.py roll --tier submarine_captain --coin-id <64-hex coin id> `
    --salt-file test.salt --pass-ordinal 1 --start-index 1
python engine/chest_roller.py verify --manifest "output/chests/<manifest>.json" --salt-file test.salt

# 6. Generate CHIP-0007 metadata for a chest manifest
python engine/metadata_gen.py --manifest "output/chests/<manifest>.json" --outdir output/metadata

# 7. Run the whole pipeline end-to-end
python scripts/run_pipeline.py

# 8. Tests
pytest
```

## Fairness in one paragraph

Before mint, we publish `SHA-256(traits.json + weights.json + tiers.json + grail
placements + RNG algorithm + secret salt)`. Every chest is rolled from
`HMAC-SHA256(salt, payment_coin_id)` — deterministic, per-purchase, and
impossible to manipulate after the commitment. After mint, the salt is revealed
and anyone can recompute every chest with `chest_roller.py verify`. See
[docs/](docs/) and ADRs for the full scheme.

## Engineering conventions

- Python 3.11+; core engine uses **stdlib + Pillow + numpy only**; no network
  calls anywhere in the generation path.
- Determinism is non-negotiable: identical inputs → byte-identical manifests
  across runs and machines. Tests prove it.
- Config-driven everything: no trait names, weights, prices, or odds hardcoded
  in Python.
- Every script is an explicit argparse CLI with clear logging; `--dry-run`
  where destructive.
- SPDX `MIT` header in every source file. An ADR for every significant decision.
- Testnet-first: anything that will touch the chain is designed for testnet11
  dry runs.

## Status

Technical core (P2–P6) built and tested. P7 (fulfillment daemon) and P8
(reveal web app) are interface stubs with design docs — see
[docs/TODO-P7-fulfillment.md](docs/TODO-P7-fulfillment.md) and
[docs/TODO-P8-reveal-app.md](docs/TODO-P8-reveal-app.md).
Sprites are **placeholders** pending final art.

## License

MIT — see [LICENSE](LICENSE).
