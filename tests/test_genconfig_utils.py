# SPDX-License-Identifier: MIT
"""Tests for GenConfig loading and cross-file consistency checks (shipgen/config.py)."""
from __future__ import annotations

from shipgen.config import GenConfig



def test_genconfig_loads_default_configs():
    cfg = GenConfig()
    assert len(cfg.layers) == 12
    assert "castaway" in cfg.tiers
    assert cfg.config_hash is not None
    assert len(cfg.config_hash) == 64
    assert cfg.weight_of("hat", "The Torn") == 0


def test_genconfig_without_weights():
    cfg = GenConfig(require_weights=False)
    assert cfg.weights is None
    assert cfg.config_hash is None


def test_genconfig_weight_of_lookup(cfg):
    w = cfg.weight_of("body", "Green")
    assert isinstance(w, int)
    assert w > 0
