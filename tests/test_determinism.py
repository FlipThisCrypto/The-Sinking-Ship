# SPDX-License-Identifier: MIT
"""Determinism is the highest-priority property of the roller (spec 5.4)."""
import json

from conftest import TEST_SALT, COIN_A, COIN_B

from shipgen.canon import canon_json, hash_obj
from shipgen.config import GenConfig
from shipgen.roll import RollEngine, derive_placements


def roll(engine, placements, coin, tier="submarine_captain", ordinal=1, start=1000):
    return engine.roll_chest(TEST_SALT, coin, tier, ordinal, start,
                             placements, "prov-test")


def test_same_inputs_byte_identical(engine, placements):
    a = roll(engine, placements, COIN_A)
    b = roll(engine, placements, COIN_A)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_fresh_engine_instance_identical(cfg, engine, placements):
    a = roll(engine, placements, COIN_A)
    b = roll(RollEngine(GenConfig()), derive_placements(TEST_SALT, cfg), COIN_A)
    assert canon_json(a) == canon_json(b)


def test_different_coins_differ(engine, placements):
    a = roll(engine, placements, COIN_A)
    b = roll(engine, placements, COIN_B)
    assert a["manifest_hash"] != b["manifest_hash"]


def test_coin_id_formatting_never_changes_roll(engine, placements):
    a = roll(engine, placements, "0x" + COIN_A.upper())
    b = roll(engine, placements, COIN_A)
    assert canon_json(a) == canon_json(b)


def test_manifest_hash_is_hash_of_body(engine, placements):
    m = roll(engine, placements, COIN_A)
    body = {k: v for k, v in m.items() if k != "manifest_hash"}
    assert m["manifest_hash"] == hash_obj(body)


def test_golden_manifest_hash(engine, placements):
    """Cross-machine/version lock. A failure means published chests would no
    longer verify — never update the expected hash after the salt commitment
    is public; bump the engine version and re-commit instead."""
    m = roll(engine, placements, COIN_A, tier="castaway", ordinal=7, start=42)
    # Bumped when tiers.json notes/OQ resolutions change config_version_hash.
    assert m["manifest_hash"] == \
        "87c48dc4d9b0d1a2651f5667f53c4c55a09183eda714b82a3e86226b6efcc710"


def test_golden_commitment_hash(commitment):
    # Bumped when tiers.json notes/OQ resolutions change the config bundle.
    assert commitment["commitment_hash"] == \
        "65e9a098abaae1a26f96e33eb008457a620188d29451f06ea54979bb58ec8a6e"


def test_placements_deterministic(cfg):
    a = derive_placements(TEST_SALT, cfg)
    b = derive_placements(TEST_SALT, cfg)
    assert canon_json(a) == canon_json(b)
    c = derive_placements(b"a-different-salt-entirely-000001", cfg)
    assert canon_json(a) != canon_json(c)


def test_commitment_covers_configs_and_salt(cfg, commitment):
    doc = commitment["commitment"]
    assert doc["config_hash"] == cfg.config_hash
    assert doc["salt_hex"] == TEST_SALT.hex()
    assert doc["rng_algorithm"] == "HMAC-SHA256-DRBG-v1"
    assert hash_obj(doc) == commitment["commitment_hash"]
