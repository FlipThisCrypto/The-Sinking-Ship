# SPDX-License-Identifier: MIT
"""Fulfillment orchestration: poll → record → budget → roll → mint → offer → audit."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from shipgen.config import GenConfig
from shipgen.roll import RollEngine, build_commitment

from .types import (
    FulfillmentLedger,
    OfferBuilder,
    PaymentSource,
    PaymentState,
)

log = logging.getLogger("fulfillment.daemon")


class FulfillmentDaemon:
    """Testnet-first daemon. Wallet mint is behind OfferBuilder (dry-run safe)."""

    def __init__(
        self,
        source: PaymentSource,
        ledger: FulfillmentLedger,
        offers: OfferBuilder,
        salt: bytes,
        cfg: GenConfig | None = None,
        network: str = "testnet11",
        strategy: str = "claim",
        did: str = "did:chia:testnet-placeholder",
        royalty_basis_points: int = 300,
        manifest_outdir: str | Path = "output/fulfillment/chests",
        metadata_outdir: str | Path = "output/fulfillment/metadata",
    ):
        if strategy not in ("claim", "stm"):
            raise ValueError("strategy must be 'claim' (default) or 'stm'")
        if strategy == "stm":
            raise NotImplementedError(
                "stm-embedded fulfillment is reserved; default strategy is "
                "'claim' (roll after CONFIRMED) for blind-mint opacity")
        self.source = source
        self.ledger = ledger
        self.offers = offers
        self.salt = salt
        self.cfg = cfg or GenConfig()
        self.engine = RollEngine(self.cfg)
        self.network = network
        self.strategy = strategy
        self.did = did
        self.royalty_basis_points = royalty_basis_points
        self.manifest_outdir = Path(manifest_outdir)
        self.metadata_outdir = Path(metadata_outdir)
        commitment = build_commitment(salt, self.cfg)
        self.placements = commitment["commitment"]["placements"]
        self.provenance_hash = commitment["commitment_hash"]
        self.budget = int(self.cfg.supply["public_mint_budget"])

    def tick(self, dry_run: bool = False) -> dict:
        """One poll+fulfill cycle. Returns a summary dict for ops/logging."""
        summary = {
            "recorded": 0,
            "rolled": 0,
            "fulfilled": 0,
            "refused": 0,
            "skipped": 0,
            "errors": [],
        }
        since = self.ledger.last_polled_height()
        try:
            purchases = self.source.poll_confirmed(since)
            tip = self.source.current_height()
        except Exception as e:
            # fail closed: do not advance height, do not shrink confirmed set
            log.error("payment scan incomplete — fail closed: %s", e)
            summary["errors"].append(f"poll: {e}")
            return summary

        for p in purchases:
            try:
                self.ledger.record_purchase(p)
                summary["recorded"] += 1
            except Exception as e:
                log.error("record_purchase %s: %s", p.coin_id[:12], e)
                summary["errors"].append(f"record {p.coin_id[:12]}: {e}")

        if not dry_run:
            self.ledger.set_last_polled_height(tip)

        for coin_id in self.ledger.purchases_needing_work():
            try:
                result = self._fulfill_one(coin_id, dry_run=dry_run)
                summary[result] = summary.get(result, 0) + 1
            except Exception as e:
                log.error("fulfill %s: %s", coin_id[:12], e)
                summary["errors"].append(f"fulfill {coin_id[:12]}: {e}")

        log.info(
            "tick done recorded=%d rolled=%d fulfilled=%d refused=%d errors=%d",
            summary["recorded"], summary.get("rolled", 0),
            summary["fulfilled"], summary["refused"], len(summary["errors"]),
        )
        return summary

    def _fulfill_one(self, coin_id: str, dry_run: bool = False) -> str:
        row = self.ledger.get_row(coin_id)
        if row is None:
            return "skipped"
        state = PaymentState(row["state"])
        if state == PaymentState.FULFILLED:
            return "skipped"

        manifest = self.ledger.get_manifest(coin_id)
        if manifest is None:
            start = self.ledger.peek_next_start_index()
            ordinal = int(row["pass_ordinal"])
            # Budget gate before committing the roll: refuse if even a 1-NFT
            # chest would exceed remaining budget; after roll, re-check qty.
            remaining = self.budget - self.ledger.supply_consumed()
            if remaining <= 0:
                reason = f"public mint budget exhausted ({self.budget})"
                self.ledger.mark_refused(coin_id, reason, dry_run=dry_run)
                log.warning("REFUSED %s: %s", coin_id[:12], reason)
                return "refused"

            manifest = self.engine.roll_chest(
                self.salt, coin_id, row["tier_name"], ordinal, start,
                self.placements, self.provenance_hash,
            )
            if self.ledger.supply_consumed() + manifest["quantity"] > self.budget:
                reason = (
                    f"chest qty {manifest['quantity']} would exceed budget "
                    f"(consumed={self.ledger.supply_consumed()}, budget={self.budget})"
                )
                self.ledger.mark_refused(coin_id, reason, dry_run=dry_run)
                log.warning("REFUSED %s: %s", coin_id[:12], reason)
                return "refused"

            if not dry_run:
                self.manifest_outdir.mkdir(parents=True, exist_ok=True)
                path = self.manifest_outdir / (
                    f"chest_{row['tier_name']}_{coin_id[:8]}.json")
                path.write_text(
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n",
                )
            self.ledger.save_roll(coin_id, manifest, dry_run=dry_run)
            log.info("rolled %s tier=%s qty=%d hash=%s",
                     coin_id[:12], row["tier_name"], manifest["quantity"],
                     manifest["manifest_hash"][:12])
            just_rolled = True
        else:
            just_rolled = False

        # Resume: prefer persisted manifest; dry-run keeps the in-memory one.
        manifest = self.ledger.get_manifest(coin_id) or manifest
        if manifest is None:
            return "skipped"

        meta_paths = self._write_metadata_paths(manifest, dry_run=dry_run)
        launchers = self.offers.mint_nfts(
            meta_paths, self.did, self.royalty_basis_points,
            self.network, dry_run=dry_run,
        )
        offer_id = self.offers.build_claim_offer(
            launchers, row["buyer_address"], self.network, dry_run=dry_run,
        )
        self.ledger.mark_fulfilled(
            coin_id, manifest["manifest_hash"], offer_id, dry_run=dry_run,
        )
        log.info("fulfilled %s offer=%s…", coin_id[:12], offer_id[:24])
        # Count "rolled" only when this tick performed the roll (ops visibility).
        return "rolled" if just_rolled and dry_run else "fulfilled"

    def _write_metadata_paths(self, manifest: dict, dry_run: bool) -> list[str]:
        """Write CHIP-0007 stubs or real metadata; return paths for mint step."""
        # Lazy import so unit tests without full metadata stack still load daemon
        from metadata_gen import MetadataGenerator

        if dry_run:
            return [
                f"dryrun/{e['global_index']:05d}.json"
                for e in manifest["nfts"] if e["type"] == "generated"
            ]

        gen = MetadataGenerator()
        self.metadata_outdir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for entry in manifest["nfts"]:
            if entry["type"] != "generated":
                continue
            doc = gen.nft_metadata(manifest, entry)
            path = self.metadata_outdir / f"{entry['global_index']:05d}.json"
            path.write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8", newline="\n",
            )
            paths.append(str(path))
        return paths
