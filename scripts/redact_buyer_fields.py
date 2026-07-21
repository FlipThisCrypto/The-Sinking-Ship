# SPDX-License-Identifier: MIT
"""Redact buyer addresses from ledger JSON dumps for public post-mortems."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
def redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k,v in obj.items():
            if k in ("buyer_address", "buyer"):
                out[k] = "***REDACTED***"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
    Path(args.out).write_text(json.dumps(redact(doc), indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": args.out}))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
