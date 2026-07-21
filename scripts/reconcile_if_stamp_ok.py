# SPDX-License-Identifier: MIT
"""Abort reconcile if config stamp mismatches (post-mint-open safety)."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--salt-file", required=True)
    ap.add_argument("--fixture", default=None)
    ap.add_argument("--coinset-url", default=None)
    args = ap.parse_args()
    r = subprocess.run([sys.executable, str(ROOT/"scripts"/"check_config_stamp.py"), "--stamp", args.stamp], cwd=str(ROOT))
    if r.returncode != 0:
        print(json.dumps({"aborted": True, "reason": "config_stamp_mismatch"}))
        return 2
    cmd = [sys.executable, str(ROOT/"engine"/"fulfillment_daemon.py"), "reconcile", "--db", args.db, "--salt-file", args.salt_file, "--loops", "1"]
    if args.fixture:
        cmd += ["--fixture", args.fixture]
    if args.coinset_url:
        cmd += ["--coinset-url", args.coinset_url]
    return subprocess.call(cmd, cwd=str(ROOT))
if __name__ == "__main__":
    raise SystemExit(main())
