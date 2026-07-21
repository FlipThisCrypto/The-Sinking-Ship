# Contributing to THE SINKING SHIP

## Before you open a PR

```bash
pip install -r requirements.txt
python -m ruff check .
python scripts/check_no_secrets.py
python scripts/check_site_links.py
python engine/validate_configs.py
python engine/render_engine.py --validate-sprites
python -m pytest tests/ -q
python scripts/smoke_fulfillment.py
# optional full mirror of CI:
# make ci
```

Fairness parity (requires Node 20+):

```bash
python scripts/export_fairness_vectors.py
node site/js/verify_vectors.mjs
```

If `site/fairness_vectors.json` changes, **commit it in the same PR**.

## Non-negotiables

1. **Determinism** — identical salt + coin + configs → byte-identical manifests.
2. **Config-driven** — no trait names, weights, prices, or odds hardcoded in Python.
3. **Fail-closed payments** — never advance ledger height on incomplete chain scans.
4. **No secrets** — never commit `*.salt`, PEMs, or `.env` files.
5. **Testnet-first** — live mainnet fulfillment requires `--allow-mainnet`.

## Design changes

Significant behavior changes need an ADR under `docs/adr/`. Spec disputes:
`sinking-ship-master-spec.md` wins over code until an ADR records the override.

## Scope tips

| Area | Start here |
|---|---|
| Roll / fairness | `engine/shipgen/`, `tests/test_determinism.py` |
| Fulfillment | `engine/fulfillment/`, `docs/TODO-P7-fulfillment.md` |
| Site | `site/`, `scripts/build_site_data.py` |
| Art / render | `engine/render_engine.py`, `sprites/`, ADR-0008 |

## Operator tooling (mint window)

```bash
python scripts/generate_salt.py --out secrets/mint.salt
python scripts/ops_preflight.py --salt-file secrets/mint.salt --db path/to/ledger.sqlite
python engine/fulfillment_daemon.py status --db path --health
python engine/fulfillment_daemon.py status --db path --metrics --out metrics.prom
python engine/fulfillment_daemon.py backup --db path --out backups/ledger.sqlite
python scripts/soak_fulfillment.py --purchases 40
python scripts/export_buyer_receipt.py --db path --coin-id <hex> --out receipt.json
```

Prefer `--log-json` on daemon commands when shipping logs to an aggregator.

## Security

See [SECURITY.md](SECURITY.md). Do not file public issues with salts or keys.
