# SPDX-License-Identifier: MIT
"""Backward-compatible re-export of P7 fulfillment interfaces.

Implementation lives in `engine/fulfillment/`. See docs/TODO-P7-fulfillment.md.
"""
from __future__ import annotations

from fulfillment import (  # noqa: F401
    CoinsetPollingSource,
    DryRunOfferBuilder,
    FixturePaymentSource,
    FulfillmentDaemon,
    FulfillmentLedger,
    OfferBuilder,
    PaymentSource,
    PaymentState,
    SqliteLedger,
    StmWebhookIngest,
    TierPurchase,
)

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
    "FulfillmentDaemon",
]
