# SPDX-License-Identifier: MIT
"""Shared types and abstract interfaces for the fulfillment daemon."""
from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import Enum


class PaymentState(str, Enum):
    DISPENSED = "dispensed"      # pass offer handed out; nothing on-chain
    PENDING = "pending"          # client reported a take (hint, untrusted)
    CONFIRMED = "confirmed"      # daemon observed the spend on-chain
    ROLLED = "rolled"            # chest rolled + manifest stored (resume point)
    EXPIRED = "expired"          # pending TTL elapsed; slot returned to pool
    FULFILLED = "fulfilled"      # mint + claim offer + audit complete
    REFUSED = "refused"          # supply budget or policy rejection


@dataclass(frozen=True)
class TierPurchase:
    """One on-chain-confirmed pass purchase (before ledger ordinal assignment)."""
    coin_id: str
    tier_name: str
    buyer_address: str
    block_height: int
    network: str


class PaymentSource(abc.ABC):
    """Payment confirmation adapter.

    Implementations:
      - FixturePaymentSource — offline dry runs
      - CoinsetPollingSource — fail-closed chain truth (primary production path)
      - StmWebhookSource — optional hint accelerator only
    """

    @abc.abstractmethod
    def poll_confirmed(self, since_height: int) -> list[TierPurchase]:
        """Return newly CONFIRMED purchases at/after height.

        MUST raise (not return partial data) if the scan is incomplete —
        the ledger only ever grows from complete scans (ADR-0001).
        """

    @abc.abstractmethod
    def current_height(self) -> int: ...


class FulfillmentLedger(abc.ABC):
    """Transactional source of truth for every purchase."""

    @abc.abstractmethod
    def record_purchase(self, p: TierPurchase) -> int:
        """Idempotent: assign pass_ordinal if new; return ordinal. Never double-insert."""

    @abc.abstractmethod
    def state_of(self, coin_id: str) -> PaymentState | None: ...

    @abc.abstractmethod
    def peek_next_start_index(self) -> int: ...

    @abc.abstractmethod
    def save_roll(self, coin_id: str, manifest: dict, dry_run: bool = False) -> None:
        """Persist rolled manifest and advance the global start_index. Resume-safe."""

    @abc.abstractmethod
    def get_manifest(self, coin_id: str) -> dict | None: ...

    @abc.abstractmethod
    def mark_fulfilled(self, coin_id: str, manifest_hash: str,
                       offer_id: str, dry_run: bool = False) -> None: ...

    @abc.abstractmethod
    def mark_refused(self, coin_id: str, reason: str, dry_run: bool = False) -> None: ...

    @abc.abstractmethod
    def supply_consumed(self) -> int:
        """NFT slots committed (rolled + fulfilled quantities)."""

    @abc.abstractmethod
    def purchases_needing_work(self) -> list[str]:
        """coin_ids in CONFIRMED or ROLLED (not yet FULFILLED/REFUSED)."""

    @abc.abstractmethod
    def get_row(self, coin_id: str) -> dict | None: ...

    @abc.abstractmethod
    def last_polled_height(self) -> int: ...

    @abc.abstractmethod
    def set_last_polled_height(self, height: int) -> None: ...


class OfferBuilder(abc.ABC):
    """Wallet-side mint + claim offer construction (Sage local RPC in production)."""

    @abc.abstractmethod
    def mint_nfts(self, metadata_paths: list[str], did: str,
                  royalty_basis_points: int, network: str,
                  dry_run: bool = False) -> list[str]:
        """Mint from the project DID; returns launcher ids."""

    @abc.abstractmethod
    def build_claim_offer(self, launcher_ids: list[str], buyer_address: str,
                          network: str, dry_run: bool = False) -> str:
        """Returns offer text ('offer1...')."""
