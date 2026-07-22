# SPDX-License-Identifier: MIT
"""Verify relative markdown links across project documentation resolve on disk.

Usage:
    python scripts/check_doc_links.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def check_link(doc_path: Path, target_str: str) -> str | None:
    target_str = target_str.strip()
    if not target_str or target_str.startswith(("#", "http://", "https://", "mailto:", "data:", "javascript:")):
        return None

    parsed = urlparse(target_str)
    if parsed.scheme in ("http", "https"):
        return None

    path_part = unquote(parsed.path)
    if not path_part:
        return None  # anchor-only link within same file

    candidate = (doc_path.parent / path_part).resolve()
    if not candidate.exists():
        return f"{doc_path.relative_to(ROOT)}: link '{target_str}' -> '{candidate}' does not exist"
    return None


def main() -> int:
    md_files = sorted(ROOT.glob("*.md")) + sorted(ROOT.glob("docs/**/*.md"))
    missing: list[str] = []
    checked_count = 0

    for md in md_files:
        if ".pytest_cache" in md.parts or ".ruff_cache" in md.parts:
            continue
        text = md.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group(2)
            err = check_link(md, target)
            if err:
                missing.append(err)
            else:
                checked_count += 1

    if missing:
        print("check_doc_links: FAILED", file=sys.stderr)
        for err in missing:
            print(f"  {err}", file=sys.stderr)
        return 1

    print(f"check_doc_links: ok ({checked_count} local markdown links across {len(md_files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
