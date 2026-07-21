# SPDX-License-Identifier: MIT
"""Export ledger audit log with a SHA-256 integrity trailer.

Does not use private keys — provides a checksum operators can recompute to
detect silent tampering of archived audit JSON.

Usage:
    python scripts/signed_audit_export.py --db ledger.sqlite --out audit.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from fulfillment import SqliteLedger  # noqa: E402
from shipgen.config import GenConfig  # noqa: E402
from shipgen.canon import canon_json  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    led = SqliteLedger(args.db, caps)
    try:
        rows = led.export_audit(limit=args.limit)
    finally:
        led.close()

    body = {"schema": "sinking-ship-audit-export-v1", "rows": rows}
    digest = hashlib.sha256(canon_json(body).encode("utf-8")).hexdigest()
    doc = {**body, "content_sha256": digest}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"ok": True, "rows": len(rows), "content_sha256": digest}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
