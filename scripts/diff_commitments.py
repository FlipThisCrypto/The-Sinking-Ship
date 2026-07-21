# SPDX-License-Identifier: MIT
"""Compare two commitment JSON documents (pre-mint vs re-derived).

Usage:
    python scripts/diff_commitments.py a.json b.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("left")
    ap.add_argument("right")
    args = ap.parse_args()
    a = json.loads(Path(args.left).read_text(encoding="utf-8"))
    b = json.loads(Path(args.right).read_text(encoding="utf-8"))

    def dig(doc):
        if "commitment_hash" in doc:
            return doc["commitment_hash"], doc.get("commitment")
        if "commitment" in doc and isinstance(doc["commitment"], dict):
            return doc.get("commitment_hash"), doc["commitment"]
        return doc.get("hash"), doc

    ha, ca = dig(a)
    hb, cb = dig(b)
    report = {
        "left": args.left,
        "right": args.right,
        "hash_equal": ha == hb,
        "left_hash": ha,
        "right_hash": hb,
        "body_equal": ca == cb,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["hash_equal"] and report["body_equal"] else 1


if __name__ == "__main__":
    sys.exit(main())
