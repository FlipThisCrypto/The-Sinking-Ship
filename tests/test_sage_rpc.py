# SPDX-License-Identifier: MIT
"""Sage RPC client — mock transport only (no local wallet required)."""
from __future__ import annotations

import json

import pytest

from fulfillment.sage_rpc import SageOfferBuilder, SageRpcClient, SageRpcError


def test_health_via_mock():
    def http_post(url, body, headers):
        req = json.loads(body.decode())
        assert req["method"] == "health"
        return json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": {"status": "ok"}}).encode()

    c = SageRpcClient(http_post=http_post)
    h = c.health()
    assert h["ok"] is True
    assert h["result"]["status"] == "ok"


def test_rpc_error_surfaces():
    def http_post(url, body, headers):
        req = json.loads(body.decode())
        return json.dumps({
            "jsonrpc": "2.0", "id": req["id"],
            "error": {"code": -1, "message": "nope"},
        }).encode()

    c = SageRpcClient(http_post=http_post)
    with pytest.raises(SageRpcError, match="nope"):
        c.call("anything")


def test_offer_builder_dry_run_without_client():
    b = SageOfferBuilder(client=None)
    lids = b.mint_nfts(["a.json", "b.json"], "did:x", 300, "testnet11", dry_run=True)
    assert len(lids) == 2
    offer = b.build_claim_offer(lids, "txch1buyer", "testnet11", dry_run=True)
    assert offer.startswith("offer1_dryrun_")


def test_offer_builder_live_path():
    def http_post(url, body, headers):
        req = json.loads(body.decode())
        if req["method"] == "mint_nfts":
            return json.dumps({
                "jsonrpc": "2.0", "id": req["id"],
                "result": ["launcher1", "launcher2"],
            }).encode()
        if req["method"] == "build_claim_offer":
            return json.dumps({
                "jsonrpc": "2.0", "id": req["id"],
                "result": "offer1_real_demo",
            }).encode()
        raise AssertionError(req["method"])

    b = SageOfferBuilder(SageRpcClient(http_post=http_post))
    lids = b.mint_nfts(["a.json"], "did:x", 300, "testnet11", dry_run=False)
    assert lids == ["launcher1", "launcher2"]
    assert b.build_claim_offer(lids, "txch1x", "testnet11", dry_run=False) == "offer1_real_demo"


def test_health_fallback_to_ping_on_health_method_error():
    def http_post(url, body, headers):
        req = json.loads(body.decode())
        if req["method"] == "health":
            return json.dumps({
                "jsonrpc": "2.0", "id": req["id"],
                "error": {"code": -32601, "message": "Method not found"},
            }).encode()
        if req["method"] == "ping":
            return json.dumps({
                "jsonrpc": "2.0", "id": req["id"],
                "result": "pong",
            }).encode()
        raise AssertionError(req["method"])

    c = SageRpcClient(http_post=http_post)
    h = c.health()
    assert h["ok"] is True
    assert h["result"] == "pong"

