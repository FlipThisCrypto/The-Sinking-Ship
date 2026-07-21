# THE SINKING SHIP — Master Test Plan (P12)

> The systematic map from **risk → test**. Every claim the project makes to
> buyers (fair, deterministic, fail-closed, within-budget) is backed here by a
> named automated test or an explicit manual/owner gate. Pairs with the
> execution checklist in [`LAUNCH-CHECKLIST.md`](LAUNCH-CHECKLIST.md).

**Status:** complete plan (P12). The *plan and checklist are done*; the
owner/infra **execution** gates (testnet11 E2E, Sage mTLS, art cohesion, owner
sign-off) are marked as such and are the only things standing between this plan
and a mainnet go.

---

## 1. Philosophy

1. **Determinism is sacred.** Identical inputs → byte-identical manifests, on
   every machine and Python version, forever. Golden vectors are never edited
   after a salt is committed.
2. **Fail closed.** Anything touching the chain refuses ambiguous state rather
   than risk a double-fulfill or over-mint.
3. **Testnet before mainnet.** No mainnet commitment until the testnet11
   end-to-end gate is green.
4. **CI is the floor, not the ceiling.** Green CI is required to merge; launch
   requires the additional manual gates below.

---

## 2. Test surface (automated)

`pytest` — **140 tests across 40 files** — plus three CI jobs
([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)):

- **`ruff static analysis`** — lint gate, plus secret-path hygiene
  (`check_no_secrets`), site local-link check, and a `tiers.js`-vs-config
  staleness guard.
- **`tests & config validation`** (Python 3.11 + 3.13 matrix) — version assert,
  config schema validation, sprite-inventory validation, the full pytest suite,
  fulfillment smoke, a 40-purchase burst soak, a disaster-recovery drill, a
  chaos coinset fail-closed drill, the full-sellout rarity check, and the
  roll-core p95 load test.
- **`Python↔JS fairness vector parity`** — regenerates fairness vectors, fails
  if the committed copy is stale, runs the Node verifier, and checks the demo
  chest manifest shape (the reveal contract).

---

## 3. Risk → test matrix

| # | Risk (what could betray a buyer) | Primary automated coverage | Gate |
|---|---|---|---|
| R1 | Rolls not reproducible across machines/versions | `test_determinism.py`, `test_property_determinism.py`, golden manifests; 3.11+3.13 CI matrix | CI |
| R2 | Browser verifier disagrees with the engine | `Python↔JS fairness vector parity` job, `test_demo_chest_site.py`, `verify_vectors.mjs` | CI |
| R3 | Config/odds silently changed after commitment | `validate_configs`, config bundle hash, `test_config_and_schema.py`, `test_diff_commitments.py`, `stamp_config_hash`/`check_config_stamp` | CI + preflight |
| R4 | Constraint rules (exclusions/pairings/quotas/forced aura) violated | `test_constraints.py`, `test_chests.py` | CI |
| R5 | Rarity distribution drifts from spec 4.1 (±5%) | `simulate.py --check` (5 replicates) in CI | CI |
| R6 | The Torn / grail placements wrong or non-committed | `test_chests.py`, `test_determinism.py`, `derive_placements` coverage | CI |
| R7 | Grail metadata malformed or placeholder | `test_metadata.py`, `test_grail_bios.py` | CI |
| R8 | Double-pay / crash mid-fulfillment / over-mint | `test_fulfillment.py`, `test_concurrent_fixture_tick.py`, `test_reconcile_lock.py`, `test_budget_guard.py`, `test_ops_limits.py` | CI |
| R9 | Coinset/RPC outage causes wrong action instead of halt | `test_chaos_coinset.py`, `test_circuit_breaker.py`, `test_mock_coinset.py`, `test_payment_sources.py`, `test_sage_rpc.py` | CI |
| R10 | Ledger loss / no recovery path | `test_dr_drill.py`, `test_retention.py`, `dr_drill.py` in CI | CI |
| R11 | Roll core too slow under burst → stalled ticks | `load_test_rolls.py` p95 < 100ms in CI, `test_timing.py` | CI |
| R12 | Secrets (salt/keys) committed or leaked in dumps | `check_no_secrets` (CI), `test_check_no_secrets.py`, `test_redact_buyer.py`, `redact_buyer_fields` | CI |
| R13 | Observability/SLO gaps hide a failing mint | `test_metrics.py`, `test_health.py`, `test_logging_util.py`, `test_slo_doc.py`, `compare_health_jsonl` | CI + ops |
| R14 | Wrong art rendered / missing sprites | `render_engine --validate-sprites`, `test_render.py`, `test_adr0009.py` | CI |
| R15 | CLI misuse silently produces bad output | `test_chest_roller_cli.py`, `test_validate_manifest_cli.py`, `test_ci_hooks.py` | CI |
| R16 | Buyer can't get a receipt / audit trail | `test_buyer_receipt.py`, `test_alert_examples.py`, `append_decision_log` | CI |

---

## 4. Determinism proof (the crown jewel)

- **Golden vectors** in `test_determinism.py` and `site/fairness_vectors.json`
  are the frozen contract. **Never regenerate them after a public salt
  commitment** — a change means the published odds moved.
- **Cross-version:** CI runs the suite on Python 3.11 and 3.13.
- **Cross-machine:** the multi-machine determinism run is an owner gate
  (§6) — run the suite on a second OS/arch and diff manifest hashes; they must
  be identical.
- **Cross-language:** the parity job proves the browser JS DRBG reproduces the
  Python engine's KAT and seed-key derivation bit-for-bit.

---

## 5. Fulfillment resilience (chain-adjacent)

Exercised offline against fixtures/mock coinset so the whole failure surface is
testable without a node:

- **Burst soak** (`soak_fulfillment.py`, 40 purchases) — throughput + no double
  fulfill under load.
- **Disaster recovery** (`dr_drill.py`) — backup → wipe → restore → reconcile.
- **Chaos** (`chaos_coinset.py`) — inject coinset failures; assert fail-closed.
- **Circuit breaker / reconcile lock / budget guard** — no thrash, no
  concurrent double-tick, no mint past `public_mint_budget`.

---

## 6. Manual & owner/infra gates (not automatable here)

These are the remaining go/no-go items; each needs owner action or live infra.
They are **not** claimed complete by this plan:

- **Multi-machine determinism run** — second OS/arch, diff hashes.
- **Art cohesion** — `style_score.py` ≥ 92 on the final batch + owner review of
  the contact sheet; final grail 1/1 art.
- **Testnet11 E2E** — pay → detect → roll → mint DID → offer → accept →
  `chest_roller.py verify`, plus a ≥1h `reconcile` dry-run.
- **Sage mTLS** — certs bootstrapped, `SageRpcClient.health` green on testnet.
- **Chain identity** — project DID, royalty address, final collection id
  (OQ-8) in `config/collection.json` (OPS-1).
- **Commitment ceremony** — salt generated offline (`generate_salt.py`), hash
  published, mint window announced; salt custody documented.
- **Owner sign-off** — pricing + supply table, and the Scuttling ceremony
  rehearsed (`SCUTTLING-PROCEDURE.md`).

---

## 7. Pre-mint go/no-go procedure

1. CI green on the exact commit to be tagged for mint.
2. `python scripts/ops_preflight.py --salt-file secrets/mint.salt` green.
3. `python scripts/gen_gonogo_report.py --salt-file secrets/mint.salt --out output/gonogo.md`
   — attach to the launch record.
4. Walk [`LAUNCH-CHECKLIST.md`](LAUNCH-CHECKLIST.md) top-to-bottom; every box
   ticked or explicitly waived by the owner with a reason.
5. Only then: publish the commitment hash.

---

## 8. Regression policy

- A red CI run blocks merge and blocks launch — no exceptions near mint.
- Determinism goldens and `fairness_vectors.json` are append-only after
  commitment; changing them is a launch-abort event, not a routine fix.
- Any new chain-touching code ships with a fail-closed test before it merges.
