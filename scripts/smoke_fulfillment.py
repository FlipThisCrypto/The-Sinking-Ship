# SPDX-License-Identifier: MIT
"""End-to-end offline smoke: fixture payments → tick → status → verify chests.

Usage:
    python scripts/smoke_fulfillment.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "fulfillment" / "smoke"
PY = sys.executable


def run(argv: list[str]) -> None:
    print("+", " ".join(argv), flush=True)
    r = subprocess.run([PY, *argv], cwd=ROOT)
    if r.returncode != 0:
        sys.exit(r.returncode)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    salt = OUT / "test.salt"
    salt.write_bytes(b"smoke-fulfillment-salt-NOT-MAINNET-01")
    db = OUT / "ledger.sqlite"
    if db.exists():
        db.unlink()

    run([
        "engine/fulfillment_daemon.py", "tick",
        "--fixture", "fixtures/example_payments.json",
        "--salt-file", str(salt),
        "--db", str(db),
        "--manifest-outdir", str(OUT / "chests"),
        "--metadata-outdir", str(OUT / "metadata"),
    ])
    run(["engine/fulfillment_daemon.py", "status", "--db", str(db)])

    chests = sorted((OUT / "chests").glob("chest_*.json"))
    if not chests:
        print("SMOKE FAIL: no chest manifests written")
        return 1
    for c in chests:
        run([
            "engine/chest_roller.py", "verify",
            "--manifest", str(c),
            "--salt-file", str(salt),
        ])
    status = json.loads(subprocess.check_output(
        [PY, "engine/fulfillment_daemon.py", "status", "--db", str(db)],
        cwd=ROOT, text=True,
    ))
    print("SMOKE OK:", json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
