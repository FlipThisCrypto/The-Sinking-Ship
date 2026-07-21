# SPDX-License-Identifier: MIT
"""Verify content_sha256 on a sinking-ship-audit-export-v1 file."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from shipgen.canon import canon_json  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    args = ap.parse_args()
    doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
    claimed = doc.pop("content_sha256", None)
    if not claimed:
        print(json.dumps({"ok": False, "error": "missing content_sha256"}))
        return 1
    got = hashlib.sha256(canon_json(doc).encode("utf-8")).hexdigest()
    ok = got == claimed
    print(json.dumps({"ok": ok, "claimed": claimed, "got": got}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
