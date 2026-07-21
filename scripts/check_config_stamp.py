# SPDX-License-Identifier: MIT
"""Fail if live configs no longer match a stamped mint-open hash."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from shipgen.config import GenConfig  # noqa: E402
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", required=True)
    args = ap.parse_args()
    stamped = Path(args.stamp).read_text(encoding="utf-8").strip()
    live = GenConfig().config_hash
    ok = stamped == live
    print(json.dumps({"ok": ok, "stamped": stamped, "live": live}))
    return 0 if ok else 1
if __name__ == "__main__":
    raise SystemExit(main())
