# SPDX-License-Identifier: MIT
"""Tests that fulfillment __init__.py re-exports all public API symbols."""
from __future__ import annotations

import fulfillment


def test_all_public_symbols_importable():
    for name in fulfillment.__all__:
        obj = getattr(fulfillment, name, None)
        assert obj is not None, f"{name} listed in __all__ but not importable"


def test_all_expected_count():
    assert len(fulfillment.__all__) >= 17
