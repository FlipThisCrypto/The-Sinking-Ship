# SPDX-License-Identifier: MIT
"""CLI shape + quantity checks for a chest-manifest-v1 JSON file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from metadata_gen import MAX_CHEST_QUANTITY  # noqa: E402


def validate(doc: dict) -> list[str]:
    problems: list[str] = []
    if doc.get("schema") != "chest-manifest-v1":
        problems.append("schema must be chest-manifest-v1")
    nfts = doc.get("nfts")
    if not isinstance(nfts, list) or not nfts:
        problems.append("nfts must be non-empty array")
        return problems
    if doc.get("quantity") is not None and int(doc["quantity"]) != len(nfts):
        problems.append("quantity mismatch")
    if len(nfts) > MAX_CHEST_QUANTITY:
        problems.append(f"quantity > {MAX_CHEST_QUANTITY}")
    h = doc.get("manifest_hash")
    if not isinstance(h, str) or len(h) != 64:
        problems.append("manifest_hash must be 64 chars")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    args = ap.parse_args()
    doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
    problems = validate(doc)
    print(json.dumps({"path": args.path, "ok": not problems, "problems": problems}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
