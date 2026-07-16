# SPDX-License-Identifier: MIT
"""Chest-level behavior: quantities, guarantees, grails, The Torn quota."""
import hashlib

import pytest

from conftest import TEST_SALT

from shipgen import RARITY_RANK


def coin(n: int) -> str:
    return hashlib.sha256(f"chest-test-coin:{n}".encode()).hexdigest()


def test_quantity_within_range_all_tiers(engine, placements, cfg):
    for tier in cfg.tiers_doc["tiers"]:
        m = engine.roll_chest(TEST_SALT, coin(tier["id"]), tier["name"], 1, 1,
                              placements, "prov")
        gen = m["generated_count"]
        assert tier["chest_min"] <= gen <= tier["chest_max"]
        extra = 1 if (tier["guarantee"] or {}).get("guaranteed_grail") else 0
        inline = m["quantity"] - gen - extra
        assert inline >= 0


def test_roll_chest_rejects_invalid_start_index(engine, placements):
    """Global mint indices are 1-based; 0/-1 previously produced corrupt indices."""
    for bad in (0, -1, True, 1.5, "1"):
        with pytest.raises(ValueError, match="start_index"):
            engine.roll_chest(TEST_SALT, coin(1), "castaway", 1, bad,
                              placements, "prov")


def test_roll_chest_rejects_empty_salt_and_bad_placements(engine, placements):
    with pytest.raises(ValueError, match="salt"):
        engine.roll_chest(b"", coin(1), "castaway", 1, 1, placements, "prov")
    with pytest.raises(ValueError, match="placements"):
        engine.roll_chest(TEST_SALT, coin(1), "castaway", 1, 1, {}, "prov")
    with pytest.raises(ValueError, match="provenance_hash"):
        engine.roll_chest(TEST_SALT, coin(1), "castaway", 1, 1, placements, "")


@pytest.mark.parametrize("tier_name,min_tier,count", [
    ("deep_sea_diver", "rare", 1),
    ("salvage_crew", "rare", 1),
    ("submarine_captain", "epic", 1),
    ("shipwright", "epic", 2),
    ("harbormaster", "legendary", 1),
    ("admiral", "legendary", 1),
])
def test_guarantees_enforced(engine, placements, tier_name, min_tier, count):
    need = RARITY_RANK[min_tier]
    for i in range(12):
        m = engine.roll_chest(TEST_SALT, coin(1000 + i), tier_name,
                              1 + i % engine.cfg.tiers[tier_name]["passes"],
                              1, placements, "prov")
        qualifying = sum(
            1 for e in m["nfts"]
            if e["type"] == "grail" or RARITY_RANK[e["rarity_tier"]] >= need)
        assert qualifying >= count, f"{tier_name} chest {i} missed its floor"


def test_pity_flag_consistency(engine, placements):
    """Chests that needed upgrades record them; upgraded slots qualify."""
    found = 0
    for i in range(40):
        m = engine.roll_chest(TEST_SALT, coin(2000 + i), "deep_sea_diver",
                              1 + i % 700, 1, placements, "prov")
        for slot in m["pity_upgraded_slots"]:
            found += 1
            e = next(e for e in m["nfts"] if e["slot"] == slot)
            assert e["pity_upgraded"] is True
            assert RARITY_RANK[e["rarity_tier"]] >= RARITY_RANK["rare"]
    # pity is rare by design; the loop just proves the invariant when it fires


def test_wizard_chest_has_named_grail(engine, placements):
    m = engine.roll_chest(TEST_SALT, coin(3), "wizard_of_the_deep", 1, 1,
                          placements, "prov")
    grails = [e for e in m["nfts"] if e["type"] == "grail"]
    assert len(grails) == 1
    assert m["generated_count"] == 44
    assert m["quantity"] == 45
    assert grails[0]["grail_number"] == placements["grails"]["wizard"]["grail_number"][0]


def test_admiral_grail_lottery_matches_placements(engine, placements):
    seeded = placements["grails"]["admiral"]["by_pass"]
    total = 0
    for p in range(1, 6):
        m = engine.roll_chest(TEST_SALT, coin(4000 + p), "admiral", p, 1,
                              placements, "prov")
        got = sorted(e["grail_number"] for e in m["nfts"] if e["type"] == "grail")
        assert got == sorted(seeded.get(str(p), []))
        total += len(got)
    assert total == 5


def test_torn_slots_are_44_unique_committed(placements, cfg):
    slots = placements["torn_slots"]
    assert len(slots) == 44
    assert len(set(slots)) == 44
    assert all(1 <= s <= cfg.supply["generated_pool"] for s in slots)


def test_torn_override_applies_at_committed_index(engine, placements):
    slot = placements["torn_slots"][0]
    # start the chest so its first generated NFT lands exactly on the slot
    m = engine.roll_chest(TEST_SALT, coin(5), "snorkeler", 1, slot,
                          placements, "prov")
    first = next(e for e in m["nfts"] if e["type"] == "generated")
    assert first["global_index"] == slot
    assert first["the_torn"] is True
    assert first["traits"]["hat"] == "The Torn"
    assert slot in m["the_torn_indices"]


def test_torn_survives_pity_in_guaranteed_chest(engine, placements, cfg):
    """Regression: pity re-roll must never destroy a committed Torn placement.
    Force a torn index into a guaranteed tier's chest across many coins and
    assert the manifest stays internally consistent."""
    slot = placements["torn_slots"][0]
    seen_torn_in_guaranteed = 0
    for i in range(60):
        # start the chest so its first generated NFT is the committed torn slot
        m = engine.roll_chest(TEST_SALT, coin(7000 + i), "deep_sea_diver",
                              1 + i % cfg.tiers["deep_sea_diver"]["passes"],
                              slot, placements, "prov")
        listed = set(m["the_torn_indices"])
        flagged = {e["global_index"] for e in m["nfts"]
                   if e["type"] == "generated" and e.get("the_torn")}
        assert listed == flagged, "the_torn_indices disagrees with nft flags"
        for e in m["nfts"]:
            if e.get("the_torn"):
                assert e["traits"]["hat"] == "The Torn"
                assert not e["pity_upgraded"], "a committed Torn NFT was pity-re-rolled"
                seen_torn_in_guaranteed += 1
    assert seen_torn_in_guaranteed > 0, "test never exercised a torn-in-chest case"


def test_grail_placement_counts(placements):
    g = placements["grails"]
    admiral = sum(len(v) for v in g["admiral"]["by_pass"].values())
    assert admiral == 5
    assert len(g["mid"]) == 27
    assert len(g["wizard"]["grail_number"]) == 1
    assert len(g["auction"]) == 11
    all_nums = ([n for v in g["admiral"]["by_pass"].values() for n in v]
                + [m["grail_number"] for m in g["mid"]]
                + g["wizard"]["grail_number"] + g["auction"])
    assert sorted(all_nums) == list(range(1, 45))
