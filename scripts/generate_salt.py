# SPDX-License-Identifier: MIT
"""Generate a mint salt with OS CSPRNG (never commit the output).

Usage:
    python scripts/generate_salt.py --out secrets/mint.salt
    python scripts/generate_salt.py --bytes 32 --out secrets/testnet.salt
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bytes", type=int, default=32, dest="nbytes")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.nbytes < 16:
        print("error: need >= 16 bytes", file=sys.stderr)
        return 1
    path = Path(args.out)
    if path.exists() and not args.force:
        print(f"error: {path} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    data = secrets.token_bytes(args.nbytes)
    path.write_bytes(data)
    # Restrictive ACL best-effort on POSIX; Windows inherits umask-like defaults.
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print(json_ok(path, args.nbytes))
    return 0


def json_ok(path: Path, nbytes: int) -> str:
    import json
    return json.dumps({
        "ok": True,
        "path": str(path),
        "bytes": nbytes,
        "note": "Never commit this file. *.salt is gitignored.",
    })


if __name__ == "__main__":
    sys.exit(main())
