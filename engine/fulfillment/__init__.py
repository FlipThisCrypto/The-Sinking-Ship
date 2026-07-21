# SPDX-License-Identifier: MIT
"""P7 fulfillment package — ledger, payment sources, daemon orchestration.

STM surface decision (2026-07-14, ADR-0001 aligned):
  * Payment rail: pre-built Secure-the-Mint dive-pass offers (chain settles).
  * Confirmation truth: fail-closed coin-set / chain polling.
  * Webhook: optional latency hint only — never sole confirmation.
  * Chest delivery default: claim-style after CONFIRMED (blind-mint safe).

See docs/TODO-P7-fulfillment.md.
"""
from .types import (
    PaymentState,
    TierPurchase,
    PaymentSource,
    FulfillmentLedger,
    OfferBuilder,
)
from .ledger import SqliteLedger
from .sources import CoinsetPollingSource, FixturePaymentSource, StmWebhookIngest
from .offers import DryRunOfferBuilder
from .sage_rpc import SageOfferBuilder, SageRpcClient, SageRpcError
from .daemon import FulfillmentDaemon, load_minting_defaults
from .mock_coinset import MockCoinsetServer
from .logging_util import configure_logging, event

__all__ = [
    "PaymentState",
    "TierPurchase",
    "PaymentSource",
    "FulfillmentLedger",
    "OfferBuilder",
    "SqliteLedger",
    "FixturePaymentSource",
    "CoinsetPollingSource",
    "StmWebhookIngest",
    "DryRunOfferBuilder",
    "SageRpcClient",
    "SageOfferBuilder",
    "SageRpcError",
    "FulfillmentDaemon",
    "load_minting_defaults",
    "MockCoinsetServer",
    "configure_logging",
    "event",
]
