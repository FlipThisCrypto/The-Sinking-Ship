# SPDX-License-Identifier: MIT
"""Coinset fail-closed polling + STM webhook hint parser."""
from __future__ import annotations

import json

import pytest

from fulfillment import CoinsetPollingSource, StmWebhookIngest, SqliteLedger, PaymentState
from shipgen.config import GenConfig


def test_coinset_poll_complete():
    responses = {
        "http://coinset.test/height": b'{"height": 50}',
        "http://coinset.test/purchases?since_height=10&complete=1": json.dumps({
            "complete": True,
            "purchases": [{
                "coin_id": "aa" * 32,
                "tier_name": "castaway",
                "buyer_address": "txch1abc",
                "block_height": 12,
            }],
        }).encode(),
    }

    def http_get(url: str) -> bytes:
        return responses[url]

    src = CoinsetPollingSource("http://coinset.test", http_get=http_get)
    assert src.current_height() == 50
    got = src.poll_confirmed(10)
    assert len(got) == 1
    assert got[0].coin_id == "aa" * 32


def test_coinset_fail_closed_on_incomplete():
    def http_get(url: str) -> bytes:
        if url.endswith("/height"):
            return b'{"height": 9}'
        return b'{"complete": false, "purchases": []}'

    src = CoinsetPollingSource("http://x", http_get=http_get)
    with pytest.raises(RuntimeError, match="fail closed|incomplete"):
        src.poll_confirmed(0)


def test_coinset_fail_closed_on_transport_error():
    def http_get(url: str) -> bytes:
        raise OSError("connection reset")

    src = CoinsetPollingSource("http://x", http_get=http_get)
    with pytest.raises(RuntimeError, match="incomplete"):
        src.current_height()


def test_coinset_timeout_and_user_agent_defaults():
    """Operators can tune timeout; default client identifies this project."""
    from fulfillment.sources import DEFAULT_HTTP_TIMEOUT_S, DEFAULT_USER_AGENT

    src = CoinsetPollingSource("http://coinset.test", timeout_s=12.5)
    assert src.timeout_s == 12.5
    assert DEFAULT_HTTP_TIMEOUT_S == 30.0
    assert "TheSinkingShip-fulfillment" in DEFAULT_USER_AGENT
    assert "github.com/FlipThisCrypto/The-Sinking-Ship" in DEFAULT_USER_AGENT


def test_webhook_rate_limit_and_shared_secret():
    from fulfillment import SlidingWindowRateLimiter, StmWebhookIngest

    lim = SlidingWindowRateLimiter(max_events=2, window_s=60.0)
    ingest = StmWebhookIngest(
        allowed_tiers={"castaway"},
        shared_secret="s3cret",
        rate_limiter=lim,
    )
    body = {
        "coin_id": "cc" * 32,
        "tier_name": "castaway",
        "buyer_address": "txch1buyer",
        "block_height": 1,
    }
    with pytest.raises(ValueError, match="secret"):
        ingest.parse_hint(body)
    assert ingest.parse_hint(body, headers={"X-Sinking-Ship-Secret": "s3cret"})
    body2 = dict(body)
    body2["coin_id"] = "dd" * 32
    assert ingest.parse_hint(body2, headers={"X-Sinking-Ship-Secret": "s3cret"})
    body3 = dict(body)
    body3["coin_id"] = "ee" * 32
    with pytest.raises(ValueError, match="rate limit"):
        ingest.parse_hint(body3, headers={"X-Sinking-Ship-Secret": "s3cret"})


def test_webhook_hint_never_implies_confirmed(tmp_path):
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    ledger = SqliteLedger(tmp_path / "l.sqlite", caps)
    ingest = StmWebhookIngest(
        allowed_tiers={t["name"] for t in cfg.tiers_doc["tiers"]})
    p = ingest.parse_hint({
        "coin_id": "bb" * 32,
        "tier_name": "castaway",
        "buyer_address": "txch1buyer",
        "block_height": 1,
        "confirmed": True,  # client claim — ignored
    })
    ledger.record_pending_hint(p)
    assert ledger.state_of(p.coin_id) == PaymentState.PENDING
    # promote only via record_purchase (chain truth)
    ord_ = ledger.record_purchase(p)
    assert ord_ == 1
    assert ledger.state_of(p.coin_id) == PaymentState.CONFIRMED
    ledger.close()


def test_webhook_rejects_bad_address():
    ingest = StmWebhookIngest(allowed_tiers={"castaway"})
    with pytest.raises(ValueError):
        ingest.parse_hint({
            "coin_id": "cc" * 32,
            "tier_name": "castaway",
            "buyer_address": "not-an-address",
        })
