# SPDX-License-Identifier: MIT
"""Verify local href/src targets in site/*.html resolve on disk.

Usage:
    python scripts/check_site_links.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

SITE = Path(__file__).resolve().parent.parent / "site"
ATTR_RE = re.compile(
    r"""(?ix)
    \b(?:href|src)\s*=\s*(?P<q>['"])(?P<url>.*?)(?P=q)
    """
)


def local_target(base: Path, url: str) -> Path | None:
    url = url.strip()
    if not url or url.startswith(("#", "mailto:", "data:", "javascript:")):
        return None
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        return None  # external — not checked here
    path = unquote(parsed.path)
    if path.startswith("/"):
        # site is project-pages relative; treat as site-root relative
        path = path.lstrip("/")
    # strip query/hash already via urlparse path
    candidate = (base.parent / path).resolve()
    try:
        candidate.relative_to(SITE.resolve())
    except ValueError:
        # allow resolving only under site/
        return candidate
    return candidate


def main() -> int:
    missing: list[str] = []
    checked = 0
    for html in sorted(SITE.glob("*.html")):
        text = html.read_text(encoding="utf-8")
        for m in ATTR_RE.finditer(text):
            url = m.group("url")
            target = local_target(html, url)
            if target is None:
                continue
            checked += 1
            if not target.exists():
                missing.append(f"{html.name}: missing {url} -> {target}")
    if missing:
        print("check_site_links: FAILED", file=sys.stderr)
        for line in missing:
            print(" ", line, file=sys.stderr)
        return 1
    print(f"check_site_links: ok ({checked} local refs in {len(list(SITE.glob('*.html')))} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
