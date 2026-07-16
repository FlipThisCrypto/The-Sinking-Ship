# SPDX-License-Identifier: MIT
"""Sage local wallet RPC client (mTLS-ready, testnet-first).

Default endpoint: https://127.0.0.1:9257 with optional client certs.
All HTTP is injected for unit tests — no network in CI.
"""
from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from .types import OfferBuilder

log = logging.getLogger("fulfillment.sage_rpc")

# (url, body_bytes, headers) -> response body bytes
HttpPost = Callable[[str, bytes, dict[str, str]], bytes]


class SageRpcError(RuntimeError):
    pass


class SageRpcClient:
    """Thin JSON-RPC client for Sage local API."""

    def __init__(
        self,
        base_url: str = "https://127.0.0.1:9257",
        cert_file: str | Path | None = None,
        key_file: str | Path | None = None,
        ca_file: str | Path | None = None,
        http_post: HttpPost | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.cert_file = Path(cert_file) if cert_file else None
        self.key_file = Path(key_file) if key_file else None
        self.ca_file = Path(ca_file) if ca_file else None
        self.timeout = timeout
        self._http_post = http_post
        self._rpc_id = 0

    def _ssl_context(self) -> ssl.SSLContext | None:
        if self._http_post is not None:
            return None
        ctx = ssl.create_default_context(cafile=str(self.ca_file) if self.ca_file else None)
        if self.cert_file and self.key_file:
            ctx.load_cert_chain(str(self.cert_file), str(self.key_file))
        return ctx

    def _post(self, body: dict) -> dict:
        raw = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        url = self.base_url + "/rpc" if not self.base_url.endswith("/rpc") else self.base_url
        if self._http_post is not None:
            resp = self._http_post(url, raw, headers)
        else:
            req = urllib.request.Request(url, data=raw, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(  # noqa: S310 — local Sage endpoint
                    req, timeout=self.timeout, context=self._ssl_context(),
                ) as r:
                    resp = r.read()
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                raise SageRpcError(f"Sage RPC transport failed: {e}") from e
        try:
            doc = json.loads(resp.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise SageRpcError(f"Sage RPC bad JSON: {e}") from e
        if not isinstance(doc, dict):
            raise SageRpcError("Sage RPC root must be object")
        if "error" in doc and doc["error"] is not None:
            raise SageRpcError(f"Sage RPC error: {doc['error']}")
        return doc

    def call(self, method: str, params: dict | None = None) -> object:
        self._rpc_id += 1
        doc = self._post({
            "jsonrpc": "2.0",
            "id": self._rpc_id,
            "method": method,
            "params": params or {},
        })
        return doc.get("result")

    def health(self) -> dict:
        """Best-effort health. Returns structured status; raises if unreachable."""
        try:
            result = self.call("health")
            return {"ok": True, "result": result}
        except SageRpcError:
            # Some builds use different method names — try ping.
            result = self.call("ping")
            return {"ok": True, "result": result}


class SageOfferBuilder(OfferBuilder):
    """Production OfferBuilder over SageRpcClient.

    dry_run=True never calls the wallet; returns deterministic dry-run shapes
    (same as DryRunOfferBuilder) so daemon tests stay offline-safe.
    """

    def __init__(self, client: SageRpcClient | None = None):
        self.client = client

    def mint_nfts(self, metadata_paths: list[str], did: str,
                  royalty_basis_points: int, network: str,
                  dry_run: bool = False) -> list[str]:
        if dry_run or self.client is None:
            from .offers import DryRunOfferBuilder
            return DryRunOfferBuilder().mint_nfts(
                metadata_paths, did, royalty_basis_points, network, dry_run=True)
        result = self.client.call("mint_nfts", {
            "metadata_paths": metadata_paths,
            "did": did,
            "royalty_basis_points": royalty_basis_points,
            "network": network,
        })
        if not isinstance(result, list):
            raise SageRpcError("mint_nfts result must be a list of launcher ids")
        return [str(x) for x in result]

    def build_claim_offer(self, launcher_ids: list[str], buyer_address: str,
                          network: str, dry_run: bool = False) -> str:
        if dry_run or self.client is None:
            from .offers import DryRunOfferBuilder
            return DryRunOfferBuilder().build_claim_offer(
                launcher_ids, buyer_address, network, dry_run=True)
        result = self.client.call("build_claim_offer", {
            "launcher_ids": launcher_ids,
            "buyer_address": buyer_address,
            "network": network,
        })
        if not isinstance(result, str) or not result:
            raise SageRpcError("build_claim_offer must return offer text")
        return result
