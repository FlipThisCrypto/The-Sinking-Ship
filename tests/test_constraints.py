# SPDX-License-Identifier: MIT
"""Every spec Section 3 exclusion/pairing rule holds on real rolls."""
import pytest

from conftest import TEST_SALT

N = 4000
LUCK = 3000  # deep-tier luck makes rare combos frequent enough to exercise


@pytest.fixture(scope="module")
def rolls(engine):
    return [engine.roll_nft(TEST_SALT, f"con/{i}", LUCK) for i in range(N)]


def test_ghost_body_never_burning(rolls):
    for r in rolls:
        if r.traits["body"] == "Ghost":
            assert r.traits["ship_condition"] != "Burning"


def test_fully_underwater_sea_pairing(rolls):
    for r in rolls:
        if r.traits["ship_condition"] == "Fully Underwater":
            assert r.traits["sea"] in {"Abyss", "Bioluminescent", "Black Sea"}


def test_submarine_exclusions(rolls):
    for r in rolls:
        if r.traits["ship_class"] == "Submarine":
            assert r.traits["pose"] != "On Bow"
            assert r.traits["ship_condition"] not in {"Half Sunk", "Listing"}


def test_diver_helmet_forces_no_mouth_item(rolls):
    hits = 0
    for r in rolls:
        if r.traits["hat"] == "Diver Helmet":
            hits += 1
            assert r.traits["mouth"] == "None"
    assert hits > 0, "diver helmet never rolled — test lost its teeth"


def test_ark_weather_rule(rolls):
    for r in rolls:
        if r.traits["ship_class"] == "The Ark":
            assert (r.traits["sea"] in {"Storm Swell", "Whirlpool"}
                    or r.traits["sky"] == "Heavy Rain")


def test_mythic_forces_aura(rolls):
    hits = 0
    for r in rolls:
        if r.rarity_tier == "mythic":
            hits += 1
            assert r.traits["aura"] != "None"
    assert hits > 0, "no mythic rolled at 3x luck over 4000 rolls"


def test_mythic_combo_gate(rolls):
    for r in rolls:
        combo = (r.traits["sky"] == "Blood Moon"
                 and r.traits["ship_class"] == "Ghost Ship"
                 and r.traits["scene_element"] == "Skeleton Crew")
        if combo:
            assert r.rarity_tier == "mythic"


def test_the_torn_never_weight_rolled(rolls):
    for r in rolls:
        assert r.traits["hat"] != "The Torn"


def test_rarity_tier_matches_trait_ranks(engine, rolls):
    from shipgen import RARITY_RANK
    for r in rolls[:500]:
        best = 0
        for layer, trait in r.traits.items():
            lay = engine.cfg.layer_by_name[layer]
            tr = lay.traits[lay.trait_index[trait]]
            best = max(best, max(tr.rarity_rank, 0))
        assert RARITY_RANK[r.rarity_tier] == best
