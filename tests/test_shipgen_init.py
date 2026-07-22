# SPDX-License-Identifier: MIT
"""Tests for shipgen package constants and version."""
from __future__ import annotations

import shipgen


def test_version_is_semver():
    parts = shipgen.__version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_rarity_order_and_rank():
    assert shipgen.RARITY_ORDER[0] == "common"
    assert shipgen.RARITY_ORDER[-1] == "mythic"
    assert len(shipgen.RARITY_ORDER) == 6
    assert shipgen.RARITY_RANK["common"] == 0
    assert shipgen.RARITY_RANK["mythic"] == 5
    # Strictly ascending
    for i in range(len(shipgen.RARITY_ORDER) - 1):
        a = shipgen.RARITY_ORDER[i]
        b = shipgen.RARITY_ORDER[i + 1]
        assert shipgen.RARITY_RANK[a] < shipgen.RARITY_RANK[b]
