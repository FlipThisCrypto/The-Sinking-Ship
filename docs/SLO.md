# THE SINKING SHIP — Service Level Objectives (mint window)

Measurable targets for operators and CI. Thresholds are **testnet-first** and
must be re-validated before mainnet.

| SLI | Objective | How measured | Alert when |
|---|---|---|---|
| Roll-core p95 | ≤ 100 ms / chest | `scripts/load_test_rolls.py` | p95 > 100 ms |
| Tick soak integrity | 100% fulfill of N fixture pays | `scripts/soak_fulfillment.py` | pass=false |
| Rarity distribution | ±5% relative of targets | `simulate.py --check` | exit 2 |
| Ledger integrity | PRAGMA quick_check = ok | `status` / backup | integrity_ok=false |
| Coinset poll success | Fail-closed, no height advance on error | unit + incident logs | tick errors without height stall |
| Fairness parity | Python↔JS vectors match | CI fairness-parity job | job red |
| Preflight | configs + salt + optional ledger | `ops_preflight.py` | ok=false |
| Health level | not `critical` during open mint | `status --health` | exit 2 |

## Error budgets (ops policy)

- **Roll latency:** budget allows rare p95 spikes if mean stays ≪ 10 ms offline.
- **Poll failures:** open circuit after 5 consecutive transport failures (30s cool-down);
  error budget is “no false CONFIRMED,” not “always available RPC.”
- **Budget exhaustion:** refusing with reason is **success** for safety SLI; only
  silent double-fulfill or re-roll is a reliability incident.

## Review cadence

- After every config weight change: re-run sellout `--check` + load test.
- Daily during mint: health + metrics scrape + backup.
- Post-incident: update this table if thresholds proved wrong.
