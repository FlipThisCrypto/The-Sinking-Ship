# SPDX-License-Identifier: MIT
"""Generate a one-page mint go/no-go markdown from preflight + health."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salt-file", required=True)
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cmd = [sys.executable, str(ROOT/"scripts"/"ops_preflight.py"), "--salt-file", args.salt_file, "--skip-sprites"]
    if args.db:
        cmd += ["--db", args.db]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    try:
        pre = json.loads(r.stdout)
    except json.JSONDecodeError:
        pre = {"ok": False, "raw": r.stdout}
    lines = ["# Mint go/no-go", "", f"- Preflight ok: **{pre.get('ok')}**", ""]
    for c in pre.get("checks", []):
        lines.append(f"- {c.get('check')}: {c.get('ok')} — {c.get('detail')}")
    lines.append("")
    lines.append("Sign-off: _____________ date: _____________")
    Path(args.out).write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps({"ok": pre.get("ok"), "out": args.out}))
    return 0 if pre.get("ok") else 1
if __name__ == "__main__":
    raise SystemExit(main())
