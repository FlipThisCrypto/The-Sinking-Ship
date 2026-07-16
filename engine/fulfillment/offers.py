# SPDX-License-Identifier: MIT
"""Offer builders — dry-run now; Sage mTLS client is a later P7 slice."""
from __future__ import annotations

import hashlib
import logging

from .types import OfferBuilder

log = logging.getLogger("fulfillment.offers")


class DryRunOfferBuilder(OfferBuilder):
    """No chain contact. Deterministic fake launcher ids + offer text for tests."""

    def mint_nfts(self, metadata_paths: list[str], did: str,
                  royalty_basis_points: int, network: str,
                  dry_run: bool = False) -> list[str]:
        log.info("dry-run mint_nfts n=%d did=%s network=%s dry_run=%s",
                 len(metadata_paths), did, network, dry_run)
        out = []
        for path in metadata_paths:
            h = hashlib.sha256(f"launcher:{network}:{path}".encode()).hexdigest()
            out.append(h)
        return out

    def build_claim_offer(self, launcher_ids: list[str], buyer_address: str,
                          network: str, dry_run: bool = False) -> str:
        log.info("dry-run build_claim_offer n=%d buyer=%s… network=%s",
                 len(launcher_ids), buyer_address[:12], network)
        body = hashlib.sha256(
            f"offer:{network}:{buyer_address}:{','.join(launcher_ids)}".encode()
        ).hexdigest()
        return f"offer1_dryrun_{body[:32]}"
