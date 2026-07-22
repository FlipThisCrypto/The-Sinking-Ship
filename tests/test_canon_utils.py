# SPDX-License-Identifier: MIT
"""Tests for canonical JSON serialization and hashing module (shipgen/canon.py)."""
from __future__ import annotations

from shipgen.canon import (
    canon_bytes,
    canon_json,
    config_bundle_hash,
    hash_obj,
    sha256_hex,
)


def test_canon_json_compact_separators_and_key_sorting():
    obj = {"z": 1, "a": [3, 2], "m": {"b": True, "a": None}}
    res = canon_json(obj)
    assert res == '{"a":[3,2],"m":{"a":null,"b":true},"z":1}'


def test_canon_bytes_returns_ascii():
    obj = {"title": "The Sinking Ship \u2693"}
    cb = canon_bytes(obj)
    assert isinstance(cb, bytes)
    assert b"\\u2693" in cb


def test_sha256_hex_and_hash_obj():
    h1 = sha256_hex("hello world")
    assert h1 == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    h2 = hash_obj({"key": "val"})
    assert isinstance(h2, str)
    assert len(h2) == 64


def test_config_bundle_hash():
    doc1 = {"version": "1.0"}
    doc2 = {"name": "test"}
    bh1 = config_bundle_hash(("doc1", doc1), ("doc2", doc2))
    bh2 = config_bundle_hash(("doc1", doc1), ("doc2", doc2))
    bh3 = config_bundle_hash(("doc2", doc2), ("doc1", doc1))

    assert bh1 == bh2
    assert bh1 != bh3  # Order sensitive
