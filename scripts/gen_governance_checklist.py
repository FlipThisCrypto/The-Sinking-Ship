# SPDX-License-Identifier: MIT
"""Weekly governance checklist generator (markdown) for mint post-mortems."""
from __future__ import annotations
import argparse
from datetime import date
from pathlib import Path
TEMPLATE = """# Mint governance checklist — {day}

- [ ] Review SLO.md metrics vs last 7d snapshots
- [ ] Confirm ledger backups exist and DR drill green
- [ ] Confirm config stamp still matches live hash
- [ ] Review refused CSV / support tickets
- [ ] Review circuit breaker opens (if any)
- [ ] Review budget burn-down / scuttle preview
- [ ] Update docs/CHANGELOG-OPS.md if behavior changed
"""
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    text = TEMPLATE.format(day=date.today().isoformat())
    Path(args.out).write_text(text, encoding="utf-8")
    print(args.out)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
