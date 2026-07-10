# TODO — P7: Offer-file fulfillment daemon (design brief)

**Status:** interface stubs only (`engine/fulfillment_stub.py`). Do NOT build
against mainnet until the testnet11 checklist at the bottom is green.

## What it is

A local Python service that turns confirmed dive-pass payments into delivered
chests: payment → deterministic roll → mint from project DID → offer file →
buyer. Spec sections 5.1/5.4 + Risk 5.

## Architecture (decided, ADR-0001)

| Concern | Decision | Provenance |
|---|---|---|
| Payment detection | Adapter (`PaymentSource`); STM webhook primary, coin-set polling fallback; **fail closed on partial scans** | BEPE reconciler bug: partial MintGarden pagination shrank the confirmed set and re-dispensed sold offers |
| State | SQLite ledger, per-coin rows, `UNIQUE(coin_id)`; three states pending→confirmed→fulfilled; append-only audit log with manifest hash | BEPE two-phase ledger (their strongest pattern), upgraded from CAS-on-JSON-blob to real transactions |
| Idempotency | `record_purchase` idempotent by coin_id; fulfillment resumable mid-crash without re-rolling; claim tokens single-use and **mandatory** | BEPE's advisory claim-token fall-through = soft-DoS; we have no legacy clients |
| Identity | launcher_id/coin_id tracked from our own mint records | BEPE regexed `#NNNN` from indexer display names — silently corruptible |
| Wallet ops | Sage local RPC, `https://127.0.0.1:9257`, mTLS client certs; both fulfillment strategies behind a flag (claim-offer vs STM-embedded) | spec Risk 5 (validated pattern) |
| Blind-mint opacity | Dispense responses carry an opaque offer id — never token number, traits, or rarity | BEPE deliberately returns traits pre-take (re-roll-for-rares); fatal for a blind mint |
| Supply budget | Refuse to dispense past `supply.public_mint_budget` (44,000) — OQ-1 hook | spec's own tier table over-allocates by ~200–400 at full sellout |

## Wallet-compat knowledge to inherit (do not rediscover)

- Sage approves only `requiredNamespaces` at WalletConnect pairing —
  `chia_takeOffer` and `chia_signMessageByAddress` must be required.
- Tri-state take-offer result classification: broadcast / rejected /
  **unclear** (Sage returns bare `{id: <64-hex>}`; some wallets ack sparsely).
  Unclear = possibly broadcast → pending, never an error to the user.
- Multi-shape response probing for addresses (`chia_getAddress` then
  `chia_getCurrentAddress`) and signatures (`publicKey|pubkey|public_key`).
- Mojo amounts as BigInt-safe strings end-to-end (1 XCH = 10^12 mojos).

## Remaining work

1. STM integration surface — **ask the owner**: webhook, polling, or offer
   files pre-built by STM tooling? (The P7 prompt anticipates this question.)
2. SQLite schema + migrations; crash-resume test (kill between roll and
   deliver, restart, assert no double-fulfillment, no re-roll).
3. Sage RPC client with mTLS cert bootstrap + health check.
4. Reconciler cron + manual `audit-on-chain` recovery command (BEPE needed
   the manual one in production).
5. Load test: 200 concurrent purchases (P7 prompt requirement); target
   p95 fulfillment < 30s with the roll itself < 100ms.
6. Ops: structured logs, dead-letter queue for failed deliveries,
   `--dry-run` on every mutating command.

## Testnet11 go/no-go checklist

- [ ] end-to-end on testnet11: pay → detect → roll → mint from DID → offer → accept → verify chest with `chest_roller.py verify`
- [ ] double-payment replay test (same coin_id twice) → single fulfillment
- [ ] crash-resume test green
- [ ] supply-budget refusal test at simulated budget edge
- [ ] load test green
- [ ] OQ-1 supply ruling applied in tiers.json
