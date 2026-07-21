# SPDX-License-Identifier: MIT
"""VACUUM and WAL checkpoint for long-running mint ledgers."""
from __future__ import annotations
import argparse, json, sqlite3, sys
from pathlib import Path
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--checkpoint", action="store_true", help="PRAGMA wal_checkpoint(TRUNCATE)")
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    try:
        before = Path(args.db).stat().st_size
        if args.checkpoint:
            row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            ck = list(row) if row else None
        else:
            ck = None
        conn.execute("VACUUM")
        conn.commit()
        after = Path(args.db).stat().st_size
        print(json.dumps({"ok": True, "bytes_before": before, "bytes_after": after, "checkpoint": ck}))
    finally:
        conn.close()
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
