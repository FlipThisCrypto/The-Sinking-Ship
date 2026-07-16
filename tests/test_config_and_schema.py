# SPDX-License-Identifier: MIT
"""Config integrity + the minimal schema validator's own behavior."""
import pytest

from shipgen.schema import validate, SchemaError
from shipgen.canon import canon_json, hash_obj


def test_all_configs_load_and_cross_validate(cfg):
    assert cfg.config_hash is not None
    assert len(cfg.layers) == 12


def test_every_trait_has_a_weight(cfg):
    for layer in cfg.layers:
        for t in layer.traits:
            assert t.name in cfg.weights[layer.name]


def test_quota_trait_weight_zero(cfg):
    assert cfg.weights["hat"]["The Torn"] == 0


def test_torn_quota_is_44(cfg):
    assert cfg.quotas[0]["count"] == 44


def test_tier_table_matches_spec_sums(cfg):
    tiers = cfg.tiers_doc["tiers"]
    # OQ-1 option B (2026-07-14): Snorkeler 3000 -> 2920
    assert sum(t["passes"] for t in tiers) == 4444 + 2920 + 1600 + 700 + 300 + 160 + 70 + 25 + 5 + 1
    assert sum(t["expected_supply"] for t in tiers) == 43999
    assert sum(t["expected_supply"] for t in tiers) <= cfg.supply["public_mint_budget"]
    revenue = sum(float(t["price_xch"]) * t["passes"] for t in tiers if t["price_xch"])
    assert round(revenue, 2) == 3389.90  # OQ-1 trim: -20 XCH vs 3409.90
    # effective cost/NFT must descend monotonically across the sold tiers
    sold = [t for t in tiers if t["price_xch"]]
    eff = [float(t["price_xch"]) / t["expected_mints"] for t in sold]
    assert all(eff[i] >= eff[i + 1] - 1e-9 for i in range(len(eff) - 1)), eff


def test_schema_validator_negatives():
    schema = {
        "type": "object",
        "required": ["a"],
        "properties": {
            "a": {"type": "integer", "minimum": 3},
            "b": {"enum": ["x", "y"]},
            "c": {"type": "string", "pattern": "^[a-z]+$"},
            "d": {"type": "array", "minItems": 2, "items": {"type": "integer"}},
        },
    }
    validate({"a": 3, "b": "x", "c": "ok", "d": [1, 2]}, schema)
    for bad in [
        {},                       # missing required
        {"a": 2},                 # below minimum
        {"a": 3, "b": "z"},       # not in enum
        {"a": 3, "c": "NOPE"},    # pattern fail
        {"a": 3, "d": [1]},       # minItems
        {"a": 3, "d": [1, "x"]},  # item type
        {"a": "3"},               # wrong type
    ]:
        with pytest.raises(SchemaError):
            validate(bad, schema)


def test_canonical_json_is_order_insensitive():
    assert canon_json({"b": 1, "a": [1, 2]}) == canon_json({"a": [1, 2], "b": 1})
    assert hash_obj({"x": {"n": 1, "m": 2}}) == hash_obj({"x": {"m": 2, "n": 1}})
