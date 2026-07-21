# SPDX-License-Identifier: MIT
"""Payment confirmation sources: fixture, fail-closed coinset poll, STM webhook hint."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

from shipgen.drbg import normalize_coin_id

from .types import PaymentSource, TierPurchase

# (url) -> response body bytes. Injectable for tests.
HttpGet = Callable[[str], bytes]


DEFAULT_HTTP_TIMEOUT_S = 30.0
DEFAULT_USER_AGENT = "TheSinkingShip-fulfillment/1.0 (+https://github.com/FlipThisCrypto/The-Sinking-Ship)"


def _default_http_get(
    url: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT_S,
    *,
    retries: int = 2,
    backoff_s: float = 0.25,
) -> bytes:
    """GET with short retries for transport blips; still fail-closed overall.

    Retries only transient transport failures. HTTP non-200 and JSON issues
    surface immediately. Callers must not advance ledger height on any raise.
    """
    import time

    last_err: Exception | None = None
    attempts = max(1, int(retries) + 1)
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": DEFAULT_USER_AGENT,
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                if getattr(resp, "status", 200) != 200:
                    raise RuntimeError(f"HTTP {resp.status} for {url}")
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt + 1 < attempts:
                time.sleep(backoff_s * (2 ** attempt))
                continue
            raise
    assert last_err is not None
    raise last_err


class FixturePaymentSource(PaymentSource):
    """Offline confirmed purchases from a JSON fixture file.

    Fixture schema (list):
      [{"coin_id": "<64 hex>", "tier_name": "castaway",
        "buyer_address": "xch1...", "block_height": 1, "network": "testnet11"}, ...]
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("fixture root must be a JSON array")
        self._purchases: list[TierPurchase] = []
        max_h = 0
        for i, item in enumerate(raw):
            try:
                coin = normalize_coin_id(item["coin_id"])
                p = TierPurchase(
                    coin_id=coin,
                    tier_name=str(item["tier_name"]),
                    buyer_address=str(item["buyer_address"]),
                    block_height=int(item["block_height"]),
                    network=str(item.get("network", "testnet11")),
                )
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f"fixture[{i}]: {e}") from e
            self._purchases.append(p)
            max_h = max(max_h, p.block_height)
        self._height = max_h

    def poll_confirmed(self, since_height: int) -> list[TierPurchase]:
        # Complete scan of a static fixture — never partial.
        return [p for p in self._purchases if p.block_height >= since_height]

    def current_height(self) -> int:
        return self._height


class CoinsetPollingSource(PaymentSource):
    """Fail-closed chain confirmation via a coinset-style HTTP API.

    Expected endpoints (operator-configured base_url):
      GET {base}/height  -> {"height": <int>}
      GET {base}/purchases?since_height=<n>&complete=1
          -> {"complete": true, "purchases": [ {...TierPurchase fields...} ]}

    If ``complete`` is missing/false, or the request fails, poll_confirmed
    **raises** — the ledger must not advance (ADR-0001 fail-closed).
    """

    def __init__(
        self,
        base_url: str,
        network: str = "testnet11",
        http_get: HttpGet | None = None,
        timeout_s: float = DEFAULT_HTTP_TIMEOUT_S,
    ):
        self.base_url = base_url.rstrip("/")
        self.network = network
        self.timeout_s = float(timeout_s)
        if http_get is not None:
            self._http_get = http_get
        else:
            def self_http_get(url: str) -> bytes:
                return _default_http_get(url, timeout=self.timeout_s)

            self._http_get = self_http_get

    def _get_json(self, path: str, query: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        try:
            raw = self._http_get(url)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RuntimeError(f"coinset scan incomplete (transport): {e}") from e
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise RuntimeError(f"coinset scan incomplete (bad JSON): {e}") from e
        if not isinstance(doc, dict):
            raise RuntimeError("coinset scan incomplete: root must be object")
        return doc

    def current_height(self) -> int:
        doc = self._get_json("/height")
        if "height" not in doc:
            raise RuntimeError("coinset scan incomplete: /height missing height")
        return int(doc["height"])

    def poll_confirmed(self, since_height: int) -> list[TierPurchase]:
        doc = self._get_json(
            "/purchases",
            {"since_height": since_height, "complete": "1"},
        )
        if doc.get("complete") is not True:
            raise RuntimeError(
                "coinset scan incomplete: response.complete is not true "
                "(fail closed — will not shrink or advance confirmed set)")
        raw_list = doc.get("purchases")
        if not isinstance(raw_list, list):
            raise RuntimeError("coinset scan incomplete: purchases must be a list")
        out: list[TierPurchase] = []
        for i, item in enumerate(raw_list):
            if not isinstance(item, dict):
                raise RuntimeError(f"coinset scan incomplete: purchases[{i}] not object")
            try:
                out.append(TierPurchase(
                    coin_id=normalize_coin_id(item["coin_id"]),
                    tier_name=str(item["tier_name"]),
                    buyer_address=str(item["buyer_address"]),
                    block_height=int(item["block_height"]),
                    network=str(item.get("network", self.network)),
                ))
            except (KeyError, TypeError, ValueError) as e:
                raise RuntimeError(
                    f"coinset scan incomplete: purchases[{i}]: {e}") from e
        return out


class SlidingWindowRateLimiter:
    """Simple in-process rate limiter (hints/min). Not a network WAF."""

    def __init__(self, max_events: int, window_s: float = 60.0):
        if max_events < 1:
            raise ValueError("max_events must be >= 1")
        self.max_events = int(max_events)
        self.window_s = float(window_s)
        self._times: list[float] = []

    def allow(self, now: float | None = None) -> bool:
        import time

        t = time.monotonic() if now is None else float(now)
        cutoff = t - self.window_s
        self._times = [x for x in self._times if x >= cutoff]
        if len(self._times) >= self.max_events:
            return False
        self._times.append(t)
        return True


class StmWebhookIngest:
    """Optional STM webhook → untrusted PENDING hints only.

    Never promotes to CONFIRMED. The daemon must re-observe on-chain via
    CoinsetPollingSource (or equivalent) before rolling a chest.
    """

    def __init__(
        self,
        network: str = "testnet11",
        allowed_tiers: set[str] | None = None,
        shared_secret: str | None = None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ):
        self.network = network
        self.allowed_tiers = allowed_tiers
        self.shared_secret = shared_secret
        self.rate_limiter = rate_limiter

    def parse_hint(self, payload: dict, *, headers: dict | None = None) -> TierPurchase:
        """Validate a webhook JSON body into a TierPurchase candidate.

        Raises ValueError on malformed/untrusted shape. Caller records PENDING
        only — never rolls from this alone.
        """
        if not isinstance(payload, dict):
            raise ValueError("webhook payload must be an object")
        # Auth before rate-limit accounting so failed secrets cannot burn the
        # budget (or at least: reject before counting when secret is required).
        if self.shared_secret:
            headers = headers or {}
            provided = (
                headers.get("X-Sinking-Ship-Secret")
                or headers.get("x-sinking-ship-secret")
                or payload.get("shared_secret")
            )
            if provided != self.shared_secret:
                raise ValueError("webhook shared secret mismatch")
        if self.rate_limiter is not None and not self.rate_limiter.allow():
            raise ValueError("webhook rate limit exceeded")
        # Ignore client-supplied "confirmed" claims entirely.
        try:
            coin = normalize_coin_id(str(payload["coin_id"]))
            tier = str(payload["tier_name"])
            buyer = str(payload["buyer_address"])
            height = int(payload.get("block_height", 0))
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"invalid webhook hint: {e}") from e
        if self.allowed_tiers is not None and tier not in self.allowed_tiers:
            raise ValueError(f"tier not allowed in webhook hint: {tier}")
        if not buyer.startswith("xch") and not buyer.startswith("txch"):
            raise ValueError("buyer_address must look like a Chia bech32 address")
        return TierPurchase(
            coin_id=coin,
            tier_name=tier,
            buyer_address=buyer,
            block_height=height,
            network=str(payload.get("network", self.network)),
        )
