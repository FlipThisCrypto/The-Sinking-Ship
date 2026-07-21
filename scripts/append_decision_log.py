# SPDX-License-Identifier: MIT
"""Append-only decision log for mint window governance (local file)."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--decision", required=True)
    ap.add_argument("--actor", default="ops")
    args = ap.parse_args()
    path = Path(args.log)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": args.actor,
        "decision": args.decision,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps({"ok": True, "appended": row}))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
