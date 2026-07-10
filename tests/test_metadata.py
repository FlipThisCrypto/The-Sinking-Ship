# SPDX-License-Identifier: MIT
"""CHIP-0007 metadata generation: strictness, determinism, batch behavior."""
import json

import pytest

from conftest import TEST_SALT, COIN_A

from metadata_gen import MetadataGenerator
from shipgen.schema import validate


@pytest.fixture(scope="module")
def gen():
    return MetadataGenerator()


@pytest.fixture(scope="module")
def manifest(engine, placements, gen):
    m = engine.roll_chest(TEST_SALT, COIN_A, "submarine_captain", 1, 500,
                          placements, "prov-meta-test")
    m["config_version_hash"] = gen.cfg.config_hash
    return m


def gen_entry(manifest):
    return next(e for e in manifest["nfts"] if e["type"] == "generated")


def test_metadata_is_valid_chip0007(gen, manifest):
    doc = gen.nft_metadata(manifest, gen_entry(manifest))
    validate(doc, gen.chip_schema)  # explicit double-check
    assert doc["format"] == "CHIP-0007"
    assert doc["name"] == f"Sinking Ship #{gen_entry(manifest)['global_index']:05d}"
    assert doc["series_number"] == gen_entry(manifest)["global_index"]
    assert doc["series_total"] == 44444
    assert doc["sensitive_content"] is False


def test_required_extra_attributes_present(gen, manifest):
    doc = gen.nft_metadata(manifest, gen_entry(manifest))
    by_type = {a["trait_type"]: a["value"] for a in doc["attributes"]}
    assert by_type["rarity_tier"] == gen_entry(manifest)["rarity_tier"]
    assert by_type["depth_zone"] == "midnight"
    assert by_type["dive_tier"] == "Submarine Captain"
    assert by_type["provenance_hash"] == "prov-meta-test"


def test_none_traits_omitted(gen, manifest):
    for e in manifest["nfts"]:
        if e["type"] != "generated":
            continue
        doc = gen.nft_metadata(manifest, e)
        values = [a["value"] for a in doc["attributes"]]
        assert "None" not in values


def test_description_is_zone_appropriate_and_deterministic(gen, manifest):
    e = gen_entry(manifest)
    d1 = gen.nft_metadata(manifest, e)["description"]
    d2 = gen.nft_metadata(manifest, e)["description"]
    assert d1 == d2
    assert d1 in gen.descriptions["lines"]["midnight"]


def test_grail_entries_rejected(gen, engine, placements):
    m = engine.roll_chest(TEST_SALT, COIN_A, "wizard_of_the_deep", 1, 1,
                          placements, "prov")
    grail = next(e for e in m["nfts"] if e["type"] == "grail")
    with pytest.raises(ValueError):
        gen.nft_metadata(m, grail)


def test_process_manifest_writes_files(gen, manifest, tmp_path):
    mp = tmp_path / "chest_test.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    written, grails = gen.process_manifest(mp, tmp_path / "meta")
    files = sorted((tmp_path / "meta").glob("*.json"))
    assert written == manifest["generated_count"]
    assert len(files) == written
    # determinism: regenerate -> byte-identical
    before = files[0].read_bytes()
    gen.process_manifest(mp, tmp_path / "meta")
    assert files[0].read_bytes() == before


def test_torn_hat_renders_as_halo_plus_horns(gen, engine, placements):
    slot = placements["torn_slots"][0]
    m = engine.roll_chest(TEST_SALT, COIN_A, "snorkeler", 1, slot, placements, "prov")
    m["config_version_hash"] = gen.cfg.config_hash
    torn = next(e for e in m["nfts"] if e.get("the_torn"))
    doc = gen.nft_metadata(m, torn)
    by_type = {a["trait_type"]: a["value"] for a in doc["attributes"]}
    assert by_type["Hat"] == "Halo + Horns (The Torn)"
