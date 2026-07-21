# THE SINKING SHIP — Launch checklist (P12 core)

Work this list top-to-bottom before any mainnet salt commitment.

## A. Config & fairness

- [ ] `python engine/validate_configs.py` green
- [x] `python engine/simulate.py --profile sellout --seed launch --replicates 5 --check` green (also gated in CI with `--seed ci`)
- [ ] OQ-1/2/3/4/10/11 decisions frozen in `config/` + ADRs
- [ ] Provenance commitment plan: who holds salt, where hash is published
- [ ] `python scripts/export_fairness_vectors.py` committed to `site/`
- [ ] `node site/js/verify_vectors.mjs` PASS

## B. Art & metadata

- [x] `python engine/render_engine.py --validate-sprites` 0 errors (also gated in CI + tests/test_render.py)
- [ ] `python scripts/style_score.py --samples <batch> --threshold 92` PASS
- [ ] Cohesion contact sheet reviewed by owner
- [ ] Grail 1/1 art + final lore (not stubs) ready for 44
- [ ] CHIP-0007 sample batch validates

## C. Fulfillment (testnet11 first)

- [ ] Fixture smoke: `python scripts/smoke_fulfillment.py`
- [ ] Mock coinset → real coinset URL swap tested
- [ ] Sage mTLS certs bootstrapped; `SageRpcClient.health` green on testnet
- [ ] Double-pay / crash-resume / budget edge tests green
- [ ] `reconcile` cron dry-run for ≥1 hour without errors
- [x] Load: `python scripts/load_test_rolls.py --chests 200` p95 &lt; 100ms (also gated in CI)

## D. Site & ops

- [ ] Landing + fairness + reveal + wallet pages reviewed
- [ ] GitHub Pages deploy green
- [x] Incident runbook: RPC down, double-fulfill attempt, reveal site down (`docs/INCIDENT-RUNBOOK.md`)
- [ ] Scuttling ceremony steps rehearsed (`docs/SCUTTLING-PROCEDURE.md`)

## E. Go / no-go

- [ ] testnet11 end-to-end: pay → detect → roll → mint → offer → accept → verify
- [ ] Owner sign-off on pricing + supply table
- [ ] Salt generated offline (≥16 bytes CSPRNG); never committed
- [ ] Commitment hash published; mint window announced

## Commands quick ref

```bash
pytest
python scripts/smoke_fulfillment.py
python scripts/load_test_rolls.py
node site/js/verify_vectors.mjs
python engine/fulfillment_daemon.py reconcile --fixture fixtures/example_payments.json \
  --salt-file secrets/test.salt --db output/fulfillment/ledger.sqlite --loops 1
```
