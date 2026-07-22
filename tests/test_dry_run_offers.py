# SPDX-License-Identifier: MIT
"""Tests for DryRunOfferBuilder deterministic fake minting (fulfillment/offers.py)."""
from __future__ import annotations

from fulfillment.offers import DryRunOfferBuilder


def test_dry_run_mint_nfts_deterministic():
    b = DryRunOfferBuilder()
    paths = ["meta/0001.json", "meta/0002.json", "meta/0003.json"]
    lids = b.mint_nfts(paths, "did:chia:1abc", 1000, "testnet11")

    assert len(lids) == 3
    assert len(set(lids)) == 3  # all unique
    assert all(len(lid) == 64 for lid in lids)

    # Deterministic: same inputs => same outputs
    lids2 = b.mint_nfts(paths, "did:chia:1abc", 1000, "testnet11")
    assert lids == lids2


def test_dry_run_build_claim_offer():
    b = DryRunOfferBuilder()
    lids = ["aa" * 32, "bb" * 32]
    offer = b.build_claim_offer(lids, "xch1buyer123", "testnet11")

    assert offer.startswith("offer1_dryrun_")
    assert len(offer) > 14

    # Deterministic
    offer2 = b.build_claim_offer(lids, "xch1buyer123", "testnet11")
    assert offer == offer2

    # Different buyer => different offer
    offer3 = b.build_claim_offer(lids, "xch1other456", "testnet11")
    assert offer3 != offer
