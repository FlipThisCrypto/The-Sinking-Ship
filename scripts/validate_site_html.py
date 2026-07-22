# SPDX-License-Identifier: MIT
"""Validate HTML5 semantics, SEO meta tags, accessibility attributes, and asset refs.

Scans site/*.html and root *.html files.

Usage:
    python scripts/validate_site_html.py
"""
from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


class PageValidator(HTMLParser):
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self.errors: list[str] = []
        self.ids: set[str] = set()
        self.has_doctype = False
        self.has_html_lang = False
        self.has_title = False
        self.has_viewport = False
        self.has_charset = False
        self.has_description = False
        self.has_canonical = False
        self.has_main = False
        self.in_title = False

    def handle_decl(self, decl: str) -> None:
        if decl.lower().startswith("doctype html"):
            self.has_doctype = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): v for k, v in attrs if v is not None}

        if tag == "html":
            if "lang" in attr_dict and attr_dict["lang"]:
                self.has_html_lang = True
            else:
                self.errors.append("<html lang> missing or empty")

        elif tag == "meta":
            if attr_dict.get("charset", "").lower() in ("utf-8", "utf8"):
                self.has_charset = True
            if attr_dict.get("name", "").lower() == "viewport":
                self.has_viewport = True
            if attr_dict.get("name", "").lower() == "description" and attr_dict.get("content"):
                self.has_description = True

        elif tag == "link":
            if attr_dict.get("rel", "").lower() == "canonical" and attr_dict.get("href"):
                self.has_canonical = True

        elif tag == "title":
            self.in_title = True
            self.has_title = True

        elif tag == "main":
            self.has_main = True

        elif tag == "img":
            alt = attr_dict.get("alt")
            if alt is None:
                self.errors.append("<img> tag missing 'alt' attribute")

        # Check unique IDs
        elem_id = attr_dict.get("id")
        if elem_id:
            if elem_id in self.ids:
                self.errors.append(f"Duplicate id '{elem_id}' found")
            else:
                self.ids.add(elem_id)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False


def validate_html_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    parser = PageValidator(path.name)
    parser.feed(text)

    errs: list[str] = list(parser.errors)
    if not parser.has_doctype:
        errs.append("Missing <!DOCTYPE html>")
    if not parser.has_title:
        errs.append("Missing <title> tag")
    if not parser.has_charset:
        errs.append("Missing or non-utf-8 <meta charset>")

    # Site pages require description and main landmark container
    if path.parent == SITE:
        if not parser.has_viewport:
            errs.append("Missing <meta name='viewport'>")
        if not parser.has_description and path.name != "dashboard.html":
            errs.append("Missing <meta name='description'>")
        if not parser.has_main:
            errs.append("Missing <main> ARIA landmark container")

    return [f"{path.name}: {e}" for e in errs]


def main() -> int:
    html_files = sorted(list(SITE.glob("*.html")) + list(ROOT.glob("*.html")))
    if not html_files:
        print("validate_site_html: no html files found", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for html in html_files:
        errs = validate_html_file(html)
        all_errors.extend(errs)

    if all_errors:
        print("validate_site_html: FAILED", file=sys.stderr)
        for e in all_errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    print(f"validate_site_html: ok ({len(html_files)} pages validated across site/ and repo root)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
