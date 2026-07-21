# Ops changelog (mint-critical surface)

Track intentional behavior changes that affect operators. Product marketing
copy does not belong here.

## Round 3

- Circuit breaker on coinset transport failures (open after consecutive fails).
- Reconcile exclusive file lock (`--lock-file`, stale break).
- DR drill script and CI chaos fail-closed recovery.
- SLOs documented in `docs/SLO.md`; example Prometheus alerts under `monitoring/`.
- Partial-sellout projection and cost model scripts.
- Ledger invariant verifier; metrics JSONL snapshots.

## Round 2

- JSON logs, Prometheus metrics, health, backup, soak, preflight.
- Reveal `--reveal-outdir` and webhook rate limits.

## Policy

When you change fail-closed semantics, budget math, or lock behavior, add a
dated bullet here in the same PR.
