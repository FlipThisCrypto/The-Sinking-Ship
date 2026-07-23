# SPDX-License-Identifier: MIT
"""Continuous integrity: ledger invariants beyond PRAGMA quick_check.

Checks:
  - integrity_ok
  - supply_consumed == sum(quantity) for fulfilled+rolled rows with qty
  - no duplicate coin_ids (PK)
  - states are known enum values
  - schema_version present

Usage:
    python scripts/verify_ledger_invariants.py --db ledger.sqlite
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from fulfillment import SqliteLedger  # noqa: E402
from shipgen.config import GenConfig  # noqa: E402

KNOWN = {"pending", "confirmed", "rolled", "fulfilled", "refused"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    args = ap.parse_args()

    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    problems: list[str] = []
    led = SqliteLedger(args.db, caps)
    try:
        st = led.status_summary()
        if not st.get("integrity_ok"):
            problems.append("integrity_ok is false")
        sv = st.get("schema_version", 0)
        target = st.get("schema_target", sv)
        if sv < 1 or sv != target:
            problems.append(
                f"schema_version {sv} does not match expected target {target}"
            )
        conn = led._conn
        rows = conn.execute(
            "SELECT state, quantity FROM purchases").fetchall()
        unknown = {r[0] for r in rows if r[0] not in KNOWN}
        if unknown:
            problems.append(f"unknown states: {sorted(unknown)}")
        qty_sum = sum(int(r[1] or 0) for r in rows if r[0] in ("fulfilled", "rolled"))
        if qty_sum != int(st["supply_consumed"]):
            problems.append(
                f"supply_consumed {st['supply_consumed']} != qty sum {qty_sum}")
        # ordinals unique per tier
        dups = conn.execute(
            "SELECT tier_name, pass_ordinal, COUNT(*) c FROM purchases "
            "WHERE pass_ordinal IS NOT NULL GROUP BY tier_name, pass_ordinal "
            "HAVING c > 1"
        ).fetchall()
        if dups:
            problems.append(f"duplicate tier ordinals: {dups}")
    finally:
        led.close()

    report = {"ok": not problems, "problems": problems, "status": st}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
