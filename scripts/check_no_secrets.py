# SPDX-License-Identifier: MIT
"""Fail if tracked paths look like mint secrets or private keys.

Used in CI so a mis-added salt or PEM never lands on main. Does not scan
gitignored paths (output/, secrets/, *.salt) — only the index / worktree
files that git would ship.

Usage:
    python scripts/check_no_secrets.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Basename / path patterns that must never be committed.
FORBIDDEN_NAME = re.compile(
    r"""(?ix)
    (
      \.salt$
      | (^|/)secrets/
      | \.pem$
      | \.key$
      | id_rsa
      | \.p12$
      | \.pfx$
    )
    """
)

# Content heuristics for small text-like blobs already tracked.
FORBIDDEN_CONTENT = [
    re.compile(r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    re.compile(r"BEGIN CERTIFICATE PRIVATE"),
]


def git_ls_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "ls-files", "-z"],
        stderr=subprocess.DEVNULL,
    )
    return [p for p in out.decode("utf-8", errors="replace").split("\0") if p]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    try:
        files = git_ls_files()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"check_no_secrets: cannot list git files: {e}", file=sys.stderr)
        return 2

    bad: list[str] = []
    for rel in files:
        if FORBIDDEN_NAME.search(rel.replace("\\", "/")):
            bad.append(f"forbidden path: {rel}")
            continue
        path = root / rel
        if not path.is_file():
            continue
        # Skip large / binary assets
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > 256_000 or size == 0:
            continue
        if path.suffix.lower() in {
            ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico",
            ".woff", ".woff2", ".pdf", ".sqlite",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for rx in FORBIDDEN_CONTENT:
            if rx.search(text):
                bad.append(f"forbidden content ({rx.pattern}) in {rel}")
                break

    if bad:
        print("check_no_secrets: FAILED", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"check_no_secrets: ok ({len(files)} tracked files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
