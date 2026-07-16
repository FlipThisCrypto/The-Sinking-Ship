# SPDX-License-Identifier: MIT
"""Deterministic random bit generator: HMAC-SHA256 in counter mode.

Design (ADR-0002):
- stream_key = HMAC-SHA256(seed_key, label)  — independent named substreams
- block_i    = HMAC-SHA256(stream_key, big-endian 8-byte counter)
- integers are drawn with rejection sampling from 8-byte chunks, so every
  draw is exact integer math — no floats anywhere, hence bit-identical
  behavior on every platform and Python version.

The spec's fairness scheme (Section 5.4) publishes this algorithm as part of
the provenance commitment; the constant ALGORITHM_ID below is the string that
gets committed.
"""
from __future__ import annotations

import hmac
import hashlib

ALGORITHM_ID = "HMAC-SHA256-DRBG-v1"

_MASK64 = (1 << 64) - 1


class Drbg:
    """Deterministic byte/integer stream derived from (seed_key, label)."""

    def __init__(self, seed_key: bytes, label: str):
        self._key = hmac.new(seed_key, label.encode("ascii"), hashlib.sha256).digest()
        self._counter = 0
        self._buf = b""

    def _refill(self) -> None:
        block = hmac.new(
            self._key, self._counter.to_bytes(8, "big"), hashlib.sha256
        ).digest()
        self._counter += 1
        self._buf += block

    def _take(self, n: int) -> bytes:
        while len(self._buf) < n:
            self._refill()
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _u64(self) -> int:
        return int.from_bytes(self._take(8), "big")

    def rand_below(self, n: int) -> int:
        """Uniform integer in [0, n) via rejection sampling. n >= 1."""
        if n <= 0:
            raise ValueError("rand_below requires n >= 1")
        if n == 1:
            return 0
        limit = ((_MASK64 + 1) // n) * n
        while True:
            v = self._u64()
            if v < limit:
                return v % n

    def rand_int(self, a: int, b: int) -> int:
        """Uniform integer in [a, b] inclusive."""
        if b < a:
            raise ValueError("rand_int requires a <= b")
        return a + self.rand_below(b - a + 1)

    def weighted_index(self, weights: list[int], total: int | None = None) -> int:
        """Pick an index proportional to integer weights (zero allowed).

        `total` may be supplied when the caller has precomputed sum(weights)
        (hot-path optimization); the draw sequence is identical either way.
        Negative weights are always rejected, including when `total` is
        precomputed — previously only the total-is-None path checked them.
        """
        if total is None:
            total = 0
            for w in weights:
                if w < 0:
                    raise ValueError("negative weight")
                total += w
        else:
            # O(n) sign check only — do not re-sum; caller owns total accuracy.
            for w in weights:
                if w < 0:
                    raise ValueError("negative weight")
        if total <= 0:
            raise ValueError("all weights are zero")
        r = self.rand_below(total)
        acc = 0
        for i, w in enumerate(weights):
            acc += w
            if r < acc:
                return i
        raise AssertionError("unreachable")

    def sample_distinct(self, population: int, k: int) -> list[int]:
        """k distinct integers from [0, population), in draw order."""
        if population < 0 or k < 0:
            raise ValueError("population and k must be non-negative")
        if k > population:
            raise ValueError("sample larger than population")
        if k == 0:
            return []
        seen: set[int] = set()
        out: list[int] = []
        while len(out) < k:
            v = self.rand_below(population)
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out


def derive_seed_key(salt: bytes, coin_id_hex: str) -> bytes:
    """Spec 5.4: seed = HMAC-SHA256(secret_salt, payment_coin_id).

    coin_id is normalized (strip 0x, lowercase, 64 hex chars) and the RAW
    32 bytes are the HMAC message, so casing/prefix differences can never
    change a roll.
    """
    coin = normalize_coin_id(coin_id_hex)
    return hmac.new(salt, bytes.fromhex(coin), hashlib.sha256).digest()


def normalize_coin_id(coin_id_hex: str) -> str:
    c = coin_id_hex.strip().lower()
    if c.startswith("0x"):
        c = c[2:]
    if len(c) != 64 or any(ch not in "0123456789abcdef" for ch in c):
        raise ValueError(f"coin_id must be 32 bytes of hex, got {coin_id_hex!r}")
    return c
