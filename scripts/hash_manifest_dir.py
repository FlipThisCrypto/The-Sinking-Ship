# SPDX-License-Identifier: MIT
"""Hash-chain manifests in a directory for bulk integrity (sha256 of sorted files)."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    d = Path(args.dir)
    files = sorted(d.glob("*.json"))
    h = hashlib.sha256()
    listing = []
    for p in files:
        data = p.read_bytes()
        fh = hashlib.sha256(data).hexdigest()
        h.update(fh.encode())
        listing.append({"file": p.name, "sha256": fh, "bytes": len(data)})
    root = h.hexdigest()
    doc = {"schema": "sinking-ship-manifest-dir-hash-v1", "root_sha256": root, "files": listing}
    text = json.dumps(doc, indent=2)+"\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
