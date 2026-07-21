# SPDX-License-Identifier: MIT
"""Record the config bundle hash at mint open for later dispute resolution.

Usage:
    python scripts/stamp_config_hash.py --out secrets/mint_config_hash.txt
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from shipgen.config import GenConfig
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    cfg = GenConfig()
    h = cfg.config_hash
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(h + "\n", encoding="utf-8")
    doc = {"config_hash": h, "layers": len(cfg.layers), "tiers": len(cfg.tiers)}
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(doc, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(doc))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
