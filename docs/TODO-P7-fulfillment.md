# TODO — P7: Offer-file fulfillment daemon

**Status:** ledger + fixture + coinset poll client + webhook hint + CLI ops.
Sage mTLS mint and live testnet e2e still open. No mainnet.

## STM surface — DECIDED (2026-07-14)

| Layer | Decision |
|---|---|
| **Payment** | Pre-built **Secure the Mint dive-pass offers** |
| **Confirmation truth** | **Fail-closed coin-set / chain polling** (`CoinsetPollingSource`) |
| **Webhook** | **Optional PENDING hint only** (`StmWebhookIngest`) |
| **Chest delivery** | Default **`claim`** after CONFIRMED |

## Implemented

- [x] SQLite ledger + audit + status / refused export
- [x] Fixture payment source + example fixture
- [x] `CoinsetPollingSource` (injectable HTTP, fail-closed)
- [x] `StmWebhookIngest` → PENDING only; promote on chain confirm
- [x] Daemon tick: record → budget → roll → dry-run mint/offer → fulfill
- [x] Crash-resume + double-pay + budget refusal tests
- [x] CLI: `tick`, `status`, `export-refused`, `ingest-hint`
- [x] `scripts/smoke_fulfillment.py` offline e2e
- [x] OQ-1 / STM surface documented

## Also shipped (ops loop)

- [x] `MockCoinsetServer` + HTTP integration test
- [x] `reconcile` CLI (cron entrypoint, multi-loop)
- [x] 20-chest fixture stress tick test
- [x] `export-audit`

## Remaining

1. Point `--coinset-url` at live testnet11 API (client already fail-closed).
2. Wire `SageOfferBuilder` to real Sage mTLS certs.
3. Host cron calling `reconcile` on a schedule.
4. Full concurrent *purchase* soak under production-like I/O.
5. testnet11 go/no-go: pay → detect → roll → mint → offer → accept → verify.

## CLI

```bash
python engine/fulfillment_daemon.py tick \
  --fixture fixtures/example_payments.json \
  --salt-file output/fulfillment/test.salt \
  --db output/fulfillment/ledger.sqlite

python engine/fulfillment_daemon.py status --db output/fulfillment/ledger.sqlite
python engine/fulfillment_daemon.py export-refused --db ... --out refused.json
python engine/fulfillment_daemon.py ingest-hint --db ... --json-file hint.json

python scripts/smoke_fulfillment.py
```
