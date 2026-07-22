# SPDX-License-Identifier: MIT
"""Mock coinset HTTP server + CoinsetPollingSource end-to-end (offline)."""
from __future__ import annotations

import hashlib
import pytest

from fulfillment import (

    CoinsetPollingSource,
    DryRunOfferBuilder,
    FulfillmentDaemon,
    MockCoinsetServer,
    PaymentState,
    SqliteLedger,
    TierPurchase,
)
from shipgen.config import GenConfig


def coin(n: int) -> str:
    return hashlib.sha256(f"mock-coinset:{n}".encode()).hexdigest()


def test_mock_coinset_health_endpoint(tmp_path):
    import json
    import urllib.request

    purchases = [
        TierPurchase(coin(1), "castaway", "txch1buyerone", 10, "testnet11"),
    ]
    with MockCoinsetServer(purchases=purchases, height=7) as server:
        with urllib.request.urlopen(server.base_url + "/health", timeout=5) as resp:
            doc = json.loads(resp.read().decode())
        assert doc["ok"] is True
        assert doc["height"] == 7
        assert doc["purchases"] == 1


def test_mock_coinset_poll_and_fulfill(tmp_path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    purchases = [
        TierPurchase(coin(1), "castaway", "txch1buyerone", 10, "testnet11"),
        TierPurchase(coin(2), "snorkeler", "txch1buyertwo", 11, "testnet11"),
    ]
    with MockCoinsetServer(purchases=purchases, height=20) as server:
        src = CoinsetPollingSource(server.base_url, network="testnet11")
        assert src.current_height() == 20
        got = src.poll_confirmed(0)
        assert len(got) == 2

        ledger = SqliteLedger(tmp_path / "m.sqlite", caps)
        daemon = FulfillmentDaemon(
            source=src,
            ledger=ledger,
            offers=DryRunOfferBuilder(),
            salt=b"mock-coinset-salt-NOT-MAINNET-01",
            cfg=cfg,
            manifest_outdir=tmp_path / "chests",
            metadata_outdir=tmp_path / "meta",
        )
        summary = daemon.tick(dry_run=False)
        assert summary["fulfilled"] == 2
        assert not summary["errors"]
        assert ledger.state_of(coin(1)) == PaymentState.FULFILLED
        # second tick idempotent
        s2 = daemon.tick(dry_run=False)
        assert s2["fulfilled"] == 0
        ledger.close()


def test_mock_coinset_since_height_filter():
    purchases = [
        TierPurchase(coin(3), "castaway", "txch1a", 5, "testnet11"),
        TierPurchase(coin(4), "castaway", "txch1b", 15, "testnet11"),
    ]
    with MockCoinsetServer(purchases=purchases, height=15) as server:
        src = CoinsetPollingSource(server.base_url)
        only_new = src.poll_confirmed(10)
        assert len(only_new) == 1
        assert only_new[0].coin_id == coin(4)


def test_mock_coinset_404_on_unknown_path():
    import urllib.error
    import urllib.request

    with MockCoinsetServer() as server:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(server.base_url + "/unknown_route", timeout=5)
        assert exc_info.value.code == 404

