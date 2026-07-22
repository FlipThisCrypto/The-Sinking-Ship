# SPDX-License-Identifier: MIT
"""Tests for site SEO (sitemap.xml, robots.txt) and security.txt standards."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def test_sitemap_xml_structure_and_pages():
    sitemap = SITE / "sitemap.xml"
    assert sitemap.is_file()

    tree = ET.parse(sitemap)
    root = tree.getroot()
    assert "urlset" in root.tag

    urls = [elem.text for elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert len(urls) >= 5

    # Check key pages are listed
    pages = ["index.html", "fairness.html", "reveal.html", "wallet.html", "dashboard.html"]
    for p in pages:
        assert any(p in u for u in urls), f"{p} missing from sitemap.xml"


def test_robots_txt_references_sitemap():
    robots = SITE / "robots.txt"
    assert robots.is_file()
    text = robots.read_text(encoding="utf-8")
    assert "Sitemap:" in text
    assert "Disallow: /chests/" in text


def test_security_txt_rfc9116():
    sec_txt = SITE / ".well-known" / "security.txt"
    assert sec_txt.is_file()
    text = sec_txt.read_text(encoding="utf-8")
    assert "Contact:" in text
    assert "Canonical:" in text
