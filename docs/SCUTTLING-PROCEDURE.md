# The Scuttling — public procedure checklist

**Promise:** *Ships that never sailed are scuttled.*  
When the mint window closes, unminted public supply is permanently destroyed
with ceremony. This document is the operator runbook (P12-ready).

## Preconditions

- [ ] Mint window end time published ≥ 48h in advance
- [ ] Provenance commitment hash already public
- [ ] Fulfillment ledger backed up (SQLite + audit export)
- [ ] Final pass counts per tier recorded from ledger `status`
- [ ] Salt still secret until reveal schedule

## Execution steps

1. **Freeze sales** — stop dispensing new dive-pass offers; STM inventory closed.
2. **Drain fulfillment** — run daemon until no `confirmed`/`rolled` remain (or
   document stuck rows with `export-refused` / `export-audit`).
3. **Snapshot supply**
   - `supply_consumed` from ledger
   - generated pool indices used: `next_start_index - 1`
   - grails delivered vs auction remaining
4. **Publish final numbers** — supply salvaged, per-tier passes sold, revenue,
   Torn realized count (may be &lt; 44 if undersold — OQ-3).
5. **Scuttle unminted** — on-chain burn / retire unused mint capacity per Chia
   NFT mint tooling; publish txids.
6. **Reveal salt** — publish salt + commitment document; invite
   `chest_roller.py verify` on any chest.
7. **Retire generator** — tag release; freeze `config/` used for mint; no silent
   weight edits after reveal.
8. **Ceremony post** — short public note: final supply, scuttle txids, verify
   instructions, link to fairness page.

## What we will not do

- Re-seed The Torn after close  
- Quietly mint “leftovers” into treasury beyond disclosed reserve  
- Change weights/traits after the commitment was published  

## Commands (offline prep)

```bash
python engine/fulfillment_daemon.py status --db path/to/ledger.sqlite
python engine/fulfillment_daemon.py export-audit --db path/to/ledger.sqlite --out audit.json
python engine/fulfillment_daemon.py export-refused --db path/to/ledger.sqlite --out refused.json
```
