# SPDX-License-Identifier: MIT
"""In-process mock coinset HTTP API for offline CoinsetPollingSource tests.

Serves the two endpoints CoinsetPollingSource expects:
  GET /height
  GET /purchases?since_height=&complete=1
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .types import TierPurchase


class MockCoinsetServer:
    """Thread-backed HTTP server. Use as context manager or start/stop."""

    def __init__(self, purchases: list[TierPurchase] | None = None, height: int = 1):
        self.purchases = list(purchases or [])
        self.height = height
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url = ""

    def start(self) -> str:
        purchases = self.purchases
        height_holder = {"h": self.height}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # quiet
                return

            def do_GET(self):  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path in ("/health", "/"):
                    body = json.dumps({
                        "ok": True,
                        "service": "mock-coinset",
                        "height": height_holder["h"],
                        "purchases": len(purchases),
                    }).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if parsed.path == "/height":
                    body = json.dumps({"height": height_holder["h"]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if parsed.path == "/purchases":
                    qs = parse_qs(parsed.query)
                    since = int(qs.get("since_height", ["0"])[0])
                    complete = qs.get("complete", ["0"])[0]
                    if complete not in ("1", "true", "True"):
                        body = json.dumps({"complete": False, "purchases": []}).encode()
                    else:
                        rows = [
                            {
                                "coin_id": p.coin_id,
                                "tier_name": p.tier_name,
                                "buyer_address": p.buyer_address,
                                "block_height": p.block_height,
                                "network": p.network,
                            }
                            for p in purchases
                            if p.block_height >= since
                        ]
                        body = json.dumps({"complete": True, "purchases": rows}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        port = self._httpd.server_address[1]
        self.base_url = f"http://127.0.0.1:{port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.base_url

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def __enter__(self) -> MockCoinsetServer:
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()
