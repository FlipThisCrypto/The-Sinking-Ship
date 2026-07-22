# SPDX-License-Identifier: MIT
"""OPS-1: on-chain collection identity is real, well-formed, and gated."""
from __future__ import annotations

import json
from pathlib import Path

from shipgen.config import CONFIG_DIR
from shipgen.identity import check_chain_identity

COLLECTION = json.loads((Path(CONFIG_DIR) / "collection.json").read_text(encoding="utf-8"))


def test_real_config_identity_is_valid():
    assert check_chain_identity(COLLECTION) == []


def test_owner_values_are_wired():
    coll = COLLECTION["collection"]
    mint = COLLECTION["minting"]
    assert coll["id"] == "1fdf2873-db1f-41e1-9b6c-22cc6bac732f"
    assert mint["did"].startswith("did:chia:1")
    assert mint["royalty_address"].startswith("xch1")
    assert mint["royalty_percentage_basis_points"] == 1000  # 10%


def _base() -> dict:
    return json.loads(json.dumps(COLLECTION))  # deep copy of a known-good doc


def test_placeholder_did_rejected():
    doc = _base()
    doc["minting"]["did"] = "TODO: project DID"
    assert any("did" in p for p in check_chain_identity(doc))


def test_non_uuid_collection_id_rejected():
    doc = _base()
    doc["collection"]["id"] = "col-the-sinking-ship-v1"
    assert any("collection.id" in p for p in check_chain_identity(doc))


def test_bad_royalty_address_rejected():
    doc = _base()
    doc["minting"]["royalty_address"] = "0xnot-a-chia-address"
    assert any("royalty_address" in p for p in check_chain_identity(doc))


def test_out_of_range_royalty_rejected():
    doc = _base()
    doc["minting"]["royalty_percentage_basis_points"] = 20000
    assert any("basis_points" in p for p in check_chain_identity(doc))


def test_validate_configs_enforces_identity():
    import sys

    import validate_configs

    argv = sys.argv
    sys.argv = ["validate_configs.py"]
    try:
        assert validate_configs.main() == 0  # real config passes the CI gate
    finally:
        sys.argv = argv
