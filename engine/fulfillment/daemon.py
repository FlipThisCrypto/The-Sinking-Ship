# SPDX-License-Identifier: MIT
"""Fulfillment orchestration: poll → record → budget → roll → mint → offer → audit."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from shipgen.config import GenConfig, load_json
from shipgen.roll import RollEngine, build_commitment
from shipgen.schema import validate

from .logging_util import event
from .types import (
    FulfillmentLedger,
    OfferBuilder,
    PaymentSource,
    PaymentState,
)

log = logging.getLogger("fulfillment.daemon")


def load_minting_defaults(config_dir: Path | None = None) -> dict:
    """Read minting.did and royalty from collection.json (single source of truth)."""
    root = Path(config_dir) if config_dir else (
        Path(__file__).resolve().parent.parent.parent / "config"
    )
    doc = load_json(root / "collection.json")
    validate(doc, load_json(root / "schemas" / "collection.schema.json"))
    return doc["minting"]


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
        did: str | None = None,
        royalty_basis_points: int | None = None,
        manifest_outdir: str | Path = "output/fulfillment/chests",
        metadata_outdir: str | Path = "output/fulfillment/metadata",
        reveal_outdir: str | Path | None = None,
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
        minting = load_minting_defaults()
        # collection.json is the marketplace royalty/DID source (metadata_gen too).
        # Callers may still override for test doubles or one-off dry runs.
        self.did = minting["did"] if did is None else did
        self.royalty_basis_points = (
            int(minting["royalty_percentage_basis_points"])
            if royalty_basis_points is None
            else int(royalty_basis_points)
        )
        self.manifest_outdir = Path(manifest_outdir)
        self.metadata_outdir = Path(metadata_outdir)
        # Optional public reveal tree: site/chests/<offer-id>.json for ?offer=
        self.reveal_outdir = Path(reveal_outdir) if reveal_outdir else None
        commitment = build_commitment(salt, self.cfg)
        self.placements = commitment["commitment"]["placements"]
        self.provenance_hash = commitment["commitment_hash"]
        self.budget = int(self.cfg.supply["public_mint_budget"])

    def tick(self, dry_run: bool = False) -> dict:
        """One poll+fulfill cycle. Returns a summary dict for ops/logging."""
        from datetime import datetime, timezone

        summary = {
            "recorded": 0,
            "rolled": 0,
            "fulfilled": 0,
            "refused": 0,
            "skipped": 0,
            "errors": [],
            "network": self.network,
            "dry_run": bool(dry_run),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "public_mint_budget": self.budget,
            "supply_consumed_before": self.ledger.supply_consumed(),
        }
        since = self.ledger.last_polled_height()
        event(
            log, "tick_start",
            network=self.network, dry_run=bool(dry_run), since_height=since,
        )
        try:
            purchases = self.source.poll_confirmed(since)
            tip = self.source.current_height()
        except Exception as e:
            # fail closed: do not advance height, do not shrink confirmed set
            log.error("payment scan incomplete — fail closed: %s", e)
            summary["errors"].append(f"poll: {e}")
            event(log, "tick_fail_closed", error=str(e), since_height=since)
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
        summary["supply_consumed_after"] = self.ledger.supply_consumed()
        summary["budget_remaining"] = max(
            0, self.budget - summary["supply_consumed_after"],
        )
        event(
            log, "tick_complete",
            recorded=summary["recorded"],
            rolled=summary.get("rolled", 0),
            fulfilled=summary["fulfilled"],
            refused=summary["refused"],
            skipped=summary.get("skipped", 0),
            error_count=len(summary["errors"]),
            network=self.network,
            dry_run=bool(dry_run),
            budget_remaining=summary["budget_remaining"],
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
        if not dry_run:
            self._publish_reveal_manifest(offer_id, coin_id, manifest)
        log.info("fulfilled %s offer=%s…", coin_id[:12], offer_id[:24])
        # Count "rolled" only when this tick performed the roll (ops visibility).
        return "rolled" if just_rolled and dry_run else "fulfilled"

    def _publish_reveal_manifest(
        self, offer_id: str, coin_id: str, manifest: dict,
    ) -> None:
        """Write chest-manifest-v1 for the reveal app (?offer= id lookup)."""
        if self.reveal_outdir is None:
            return
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in offer_id)[:128]
        if not safe:
            safe = coin_id[:16]
        self.reveal_outdir.mkdir(parents=True, exist_ok=True)
        path = self.reveal_outdir / f"{safe}.json"
        path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        log.info("reveal manifest published %s", path.name)

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
