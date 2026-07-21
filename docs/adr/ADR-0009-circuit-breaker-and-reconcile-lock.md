# ADR-0009: Coinset circuit breaker and reconcile file lock

## Status

Accepted (Round 3)

## Context

Mint-window fulfillment is fail-closed on incomplete payment scans. Under a
flapping RPC, every tick can error while operators retry too aggressively.
Separately, two cron hosts can both run `reconcile` against one ledger.

## Decision

1. **CircuitBreaker** on `CoinsetPollingSource` transport/JSON failures: after
   N consecutive failures, refuse further HTTP until cool-down, then half-open
   probe. Ledger height still never advances on failure.
2. **LedgerFileLock** around `reconcile` CLI: exclusive create of `<db>.lock`
   with PID/timestamp; optional stale break for dead hosts.

## Consequences

- Monitors can alert on open circuit / lock contention.
- Dual-cron double-fulfill risk is reduced (ledger already idempotent, but
  lock prevents wasted roll work and audit noise).
- Operators must not share a lock file across unrelated ledgers.
