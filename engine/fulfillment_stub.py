# SPDX-License-Identifier: MIT
"""P7 INTERFACE STUBS — fulfillment daemon (NOT implemented this session).

These interfaces encode the architecture decided in ADR-0001 from the BEPE
LOVE production survey, so the P7 implementation session can start from a
reviewed contract instead of a blank page. See docs/TODO-P7-fulfillment.md
for the full design brief.

Trust architecture (adopted from the reference, hardened):
  - offer file IS the payment rail (Secure the Mint) — no custodial watcher
  - client claims are hints -> `pending`; only the daemon's own chain
    observation promotes to `confirmed` (three-state contract)
  - reconciler FAILS CLOSED: an incomplete chain scan may grow, never
    shrink, the confirmed set
  - claim tokens are single-use and MANDATORY (the reference's
    backwards-compat fall-through is an unauthenticated soft-DoS)
  - identity is launcher_id/coin_id from our own mint records — never
    display-name regex against a third-party indexer
  - state lives in the daemon's own transactional store (SQLite), keyed
    per token with uniqueness constraints; any KV copy is a read model

Every method that would touch the chain takes `network` ("testnet11" |
"mainnet") and every mutating method has a dry_run flag — testnet-first.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import Enum


class PaymentState(str, Enum):
    DISPENSED = "dispensed"      # offer handed out; nothing observed on-chain
    PENDING = "pending"          # client reported a take (hint, untrusted)
    CONFIRMED = "confirmed"      # daemon observed the spend on-chain
    EXPIRED = "expired"          # pending TTL elapsed; slot returned to pool
    FULFILLED = "fulfilled"      # chest rolled + offer delivered + audit-logged


@dataclass(frozen=True)
class TierPurchase:
    """One confirmed pass purchase, as the roller needs it."""
    coin_id: str            # payment coin id (64 hex) — the HMAC roll seed input
    tier_name: str          # tiers.json name
    pass_ordinal: int       # 1-based purchase sequence within the tier
    buyer_address: str      # xch1... for offer delivery
    block_height: int
    network: str


class PaymentSource(abc.ABC):
    """Adapter over the payment-detection surface (Secure the Mint / coin-set
    API / full node). STM's exact surface is external — keep this thin.

    Implementations planned: StmWebhookSource, CoinsetPollingSource (fallback,
    fail-closed), TestnetFixtureSource (dry runs from a fixtures file).
    """

    @abc.abstractmethod
    def poll_confirmed(self, since_height: int) -> list[TierPurchase]:
        """Return newly CONFIRMED tier purchases at/after the given height.
        MUST raise (not return partial data) if the scan is incomplete —
        the ledger only ever grows from complete scans (ADR-0001 B2)."""

    @abc.abstractmethod
    def current_height(self) -> int: ...


class FulfillmentLedger(abc.ABC):
    """Append-only source of truth for what happened to every purchase.
    Backing store: SQLite with UNIQUE(coin_id); every transition writes an
    audit row with timestamp, actor, and manifest hash where applicable."""

    @abc.abstractmethod
    def record_purchase(self, p: TierPurchase) -> int:
        """Idempotent: returns the existing pass_ordinal if coin_id is known,
        else assigns the next ordinal for the tier and the next global
        start_index atomically. A payment must NEVER be fulfilled twice."""

    @abc.abstractmethod
    def state_of(self, coin_id: str) -> PaymentState: ...

    @abc.abstractmethod
    def mark_fulfilled(self, coin_id: str, manifest_hash: str,
                       offer_id: str, dry_run: bool = False) -> None: ...

    @abc.abstractmethod
    def supply_consumed(self) -> int:
        """Generated + grail count so far — the OQ-1 supply budget hook:
        the daemon must refuse to dispense past supply.public_mint_budget."""


class OfferBuilder(abc.ABC):
    """Wallet-side operations over Sage's local RPC.

    Endpoint: https://127.0.0.1:9257 with mTLS client certs (spec Risk 5).
    Two fulfillment strategies behind a flag (P7 prompt):
      - "claim":  mint the rolled NFTs from the project DID, then build a
                  0-XCH claim-style offer the buyer accepts
      - "stm":    embed fulfillment per Secure the Mint's model (offer built
                  at purchase time carries the payment)
    """

    @abc.abstractmethod
    def mint_nfts(self, metadata_paths: list[str], did: str,
                  royalty_basis_points: int, network: str,
                  dry_run: bool = False) -> list[str]:
        """Mint from the project DID; returns launcher ids."""

    @abc.abstractmethod
    def build_claim_offer(self, launcher_ids: list[str], buyer_address: str,
                          network: str, dry_run: bool = False) -> str:
        """Returns offer text ('offer1...')."""


class FulfillmentDaemon:
    """Orchestration skeleton: poll -> record -> roll -> mint -> offer -> audit.

    NOT IMPLEMENTED — P7 session. The loop below documents the intended
    order of operations and idempotency points.
    """

    def __init__(self, source: PaymentSource, ledger: FulfillmentLedger,
                 offers: OfferBuilder, network: str = "testnet11"):
        self.source = source
        self.ledger = ledger
        self.offers = offers
        self.network = network

    def tick(self) -> None:
        raise NotImplementedError(
            "P7 session. Intended flow per purchase:\n"
            "  1. ledger.record_purchase (idempotent; assigns ordinal+start_index)\n"
            "  2. if state >= FULFILLED: skip (never fulfill twice)\n"
            "  3. supply budget check (OQ-1) — refuse past public_mint_budget\n"
            "  4. chest_roller roll (deterministic from coin_id)\n"
            "  5. metadata_gen for the manifest\n"
            "  6. offers.mint_nfts + build_claim_offer (or STM strategy)\n"
            "  7. deliver offer; ledger.mark_fulfilled(manifest_hash, offer_id)\n"
            "All steps re-runnable; crash between 4 and 7 must resume, not re-roll.")
