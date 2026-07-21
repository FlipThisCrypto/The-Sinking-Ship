# SPDX-License-Identifier: MIT
"""P7 fulfillment daemon CLI (testnet-first).

STM surface (decided 2026-07-14):
  Payment = pre-built Secure-the-Mint dive-pass offers.
  Confirmation truth = fail-closed chain/coin-set polling (fixture for dry runs).
  Webhook = optional hint only.
  Delivery default = claim-style after CONFIRMED.

Usage:
    python engine/fulfillment_daemon.py tick --fixture fixtures/example_payments.json \\
        --salt-file output/fulfillment/test.salt --db output/fulfillment/ledger.sqlite
    python engine/fulfillment_daemon.py status --db output/fulfillment/ledger.sqlite
    python engine/fulfillment_daemon.py export-refused --db ... --out refused.json
    python engine/fulfillment_daemon.py ingest-hint --db ... --json-file hint.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from fulfillment import (
    CoinsetPollingSource,
    DryRunOfferBuilder,
    FixturePaymentSource,
    FulfillmentDaemon,
    SqliteLedger,
    StmWebhookIngest,
    configure_logging,
)
from shipgen.config import GenConfig


# audit-export / status share ledger helpers

log = logging.getLogger("fulfillment_daemon")


def read_salt(path: str) -> bytes:
    data = Path(path).read_bytes().strip()
    if len(data) < 16:
        raise SystemExit(f"salt file {path} too short (need >= 16 bytes)")
    return data


def _ledger(args) -> tuple[GenConfig, SqliteLedger]:
    cfg = GenConfig()
    caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
    return cfg, SqliteLedger(args.db, caps)


def _source(args, cfg: GenConfig):
    if getattr(args, "coinset_url", None):
        return CoinsetPollingSource(args.coinset_url, network=args.network)
    if not getattr(args, "fixture", None):
        raise SystemExit("provide --fixture or --coinset-url")
    return FixturePaymentSource(args.fixture)


def cmd_tick(args) -> int:
    cfg, ledger = _ledger(args)
    try:
        source = _source(args, cfg)
        offers = DryRunOfferBuilder()
        daemon = FulfillmentDaemon(
            source=source,
            ledger=ledger,
            offers=offers,
            salt=read_salt(args.salt_file),
            cfg=cfg,
            network=args.network,
            strategy=args.strategy,
            manifest_outdir=args.manifest_outdir,
            metadata_outdir=args.metadata_outdir,
            reveal_outdir=getattr(args, "reveal_outdir", None),
        )
        summary = daemon.tick(dry_run=args.dry_run)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1 if summary.get("errors") else 0
    finally:
        ledger.close()


def cmd_status(args) -> int:
    from fulfillment.health import build_health
    from fulfillment.metrics import status_to_prometheus

    cfg, ledger = _ledger(args)
    try:
        summary = ledger.status_summary()
        budget = int(cfg.supply["public_mint_budget"])
        summary["public_mint_budget"] = budget
        summary["budget_remaining"] = max(0, budget - int(summary["supply_consumed"]))
        if getattr(args, "metrics", False):
            text = status_to_prometheus(summary)
            if args.out:
                Path(args.out).write_text(text, encoding="utf-8", newline="\n")
                log.info("wrote metrics -> %s", args.out)
            else:
                print(text, end="")
            return 0 if summary.get("integrity_ok", True) else 1
        if getattr(args, "health", False):
            health = build_health(
                status=summary,
                public_mint_budget=budget,
                network=getattr(args, "network", "testnet11") or "testnet11",
            )
            print(json.dumps(health, indent=2, sort_keys=True))
            return 0 if health["level"] != "critical" else 2
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if summary.get("integrity_ok", True) else 1
    finally:
        ledger.close()


def cmd_export_refused(args) -> int:
    _, ledger = _ledger(args)
    try:
        rows = ledger.list_refused()
        text = json.dumps(rows, indent=2, sort_keys=True) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8", newline="\n")
            log.info("wrote %d refused row(s) -> %s", len(rows), args.out)
        else:
            print(text, end="")
        return 0
    finally:
        ledger.close()


def cmd_ingest_hint(args) -> int:
    """Record an STM webhook / client hint as PENDING only (never rolls)."""
    from fulfillment import SlidingWindowRateLimiter

    cfg, ledger = _ledger(args)
    try:
        payload = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        allowed = {t["name"] for t in cfg.tiers_doc["tiers"]}
        limiter = None
        if getattr(args, "rate_limit", None):
            limiter = SlidingWindowRateLimiter(max_events=int(args.rate_limit))
        ingest = StmWebhookIngest(
            network=args.network,
            allowed_tiers=allowed,
            shared_secret=getattr(args, "webhook_secret", None) or None,
            rate_limiter=limiter,
        )
        purchase = ingest.parse_hint(payload)
        ledger.record_pending_hint(purchase)
        print(json.dumps({
            "ok": True,
            "state": "pending",
            "coin_id": purchase.coin_id,
            "tier_name": purchase.tier_name,
            "note": "hint only — chain poll must confirm before roll",
        }, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as e:
        log.error("%s", e)
        return 1
    finally:
        ledger.close()


def cmd_archive_fulfilled(args) -> int:
    from fulfillment.retention import archive_fulfilled

    report = archive_fulfilled(
        args.db,
        older_than_days=args.days,
        archive_path=args.out,
        dry_run=not args.apply,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def cmd_lookup(args) -> int:
    """Support lookup: full purchase + optional manifest hash by coin_id."""
    from shipgen.drbg import normalize_coin_id

    _, ledger = _ledger(args)
    try:
        coin = normalize_coin_id(args.coin_id)
        row = ledger.get_row(coin)
        if row is None:
            print(json.dumps({"found": False, "coin_id": coin}, indent=2))
            return 1
        out = {
            "found": True,
            "coin_id": coin,
            "state": row.get("state"),
            "tier_name": row.get("tier_name"),
            "pass_ordinal": row.get("pass_ordinal"),
            "buyer_address": row.get("buyer_address"),
            "block_height": row.get("block_height"),
            "manifest_hash": row.get("manifest_hash"),
            "offer_id": row.get("offer_id"),
            "quantity": row.get("quantity"),
            "refuse_reason": row.get("refuse_reason"),
            "updated_at": row.get("updated_at"),
        }
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    finally:
        ledger.close()


def cmd_backup(args) -> int:
    """Online-safe SQLite backup via the backup API (crash-consistent copy)."""
    import shutil
    import sqlite3

    src = Path(args.db)
    dest = Path(args.out)
    if not src.is_file():
        log.error("ledger not found: %s", src)
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Prefer SQLite backup API when possible for a consistent snapshot.
    try:
        src_conn = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
        dest_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            src_conn.close()
    except sqlite3.Error as e:
        log.warning("sqlite backup API failed (%s); falling back to file copy", e)
        shutil.copy2(src, dest)
    # Verify destination integrity
    cfg, ledger = _ledger(argparse.Namespace(db=str(dest)))
    try:
        ok = ledger.integrity_ok()
        summary = ledger.status_summary()
    finally:
        ledger.close()
    report = {
        "source": str(src),
        "dest": str(dest),
        "integrity_ok": ok,
        "total_purchases": summary.get("total_purchases"),
        "supply_consumed": summary.get("supply_consumed"),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if ok else 1


def cmd_export_audit(args) -> int:
    _, ledger = _ledger(args)
    try:
        rows = ledger.export_audit(limit=args.limit)
        text = json.dumps(rows, indent=2, sort_keys=True) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8", newline="\n")
            log.info("wrote %d audit row(s) -> %s", len(rows), args.out)
        else:
            print(text, end="")
        return 0
    finally:
        ledger.close()


def cmd_reconcile(args) -> int:
    """One reconcile cycle: poll payment source + fulfill (ops cron entrypoint).

    Alias of tick with explicit naming for runbooks. Optional --loops for a
    short local soak (default 1). Sleeps --interval seconds between loops.
    """
    import time

    from fulfillment.reconcile_lock import LedgerFileLock, LedgerLockError

    lock_path = getattr(args, "lock_file", None) or (str(Path(args.db)) + ".lock")
    try:
        lock = LedgerFileLock(lock_path, stale_seconds=float(getattr(args, "lock_stale_s", 3600)))
        lock.acquire()
    except LedgerLockError as e:
        log.error("%s", e)
        return 3

    cfg, ledger = _ledger(args)
    try:
        source = _source(args, cfg)
        daemon = FulfillmentDaemon(
            source=source,
            ledger=ledger,
            offers=DryRunOfferBuilder(),
            salt=read_salt(args.salt_file),
            cfg=cfg,
            network=args.network,
            strategy=args.strategy,
            manifest_outdir=args.manifest_outdir,
            metadata_outdir=args.metadata_outdir,
            reveal_outdir=getattr(args, "reveal_outdir", None),
        )
        summaries = []
        for i in range(max(1, args.loops)):
            s = daemon.tick(dry_run=args.dry_run)
            s["loop"] = i + 1
            summaries.append(s)
            log.info("reconcile loop %d/%d fulfilled=%s errors=%s",
                     i + 1, args.loops, s.get("fulfilled"), len(s.get("errors") or []))
            if i + 1 < args.loops:
                time.sleep(max(0.0, args.interval))
        print(json.dumps({"cycles": summaries, "final_status": ledger.status_summary()},
                         indent=2, sort_keys=True))
        return 1 if any(s.get("errors") for s in summaries) else 0
    finally:
        ledger.close()
        lock.release()


VERSION = "1.0.0"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"fulfillment_daemon {VERSION}")
    ap.add_argument(
        "--log-json",
        action="store_true",
        help="emit JSON log lines on stderr (alert / aggregator friendly)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("tick", help="poll source and fulfill pending purchases")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--fixture", help="JSON array of confirmed purchases")
    src.add_argument("--coinset-url", help="base URL for CoinsetPollingSource")
    p.add_argument("--salt-file", required=True)
    p.add_argument("--db", default="output/fulfillment/ledger.sqlite")
    p.add_argument("--network", default="testnet11",
                   choices=["testnet11", "mainnet"])
    p.add_argument("--strategy", default="claim", choices=["claim", "stm"])
    p.add_argument("--manifest-outdir", default="output/fulfillment/chests")
    p.add_argument("--metadata-outdir", default="output/fulfillment/metadata")
    p.add_argument(
        "--reveal-outdir",
        default=None,
        help="publish fulfilled chest JSON for reveal.html ?offer= (e.g. site/chests)",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="roll in memory / log wallet ops without persisting fulfill")
    p.add_argument(
        "--allow-mainnet",
        action="store_true",
        help="required with --network mainnet for live (non-dry-run) fulfill",
    )
    p.set_defaults(fn=cmd_tick)

    p = sub.add_parser("status", help="print ledger state counts and supply")
    p.add_argument("--db", default="output/fulfillment/ledger.sqlite")
    p.add_argument(
        "--metrics",
        action="store_true",
        help="emit Prometheus text exposition instead of JSON",
    )
    p.add_argument(
        "--health",
        action="store_true",
        help="emit composite health document (ok/degraded/critical)",
    )
    p.add_argument("--out", default=None, help="with --metrics: write to file")
    p.add_argument("--network", default="testnet11", help="label for --health")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("export-refused", help="export refused purchases (dead letter)")
    p.add_argument("--db", default="output/fulfillment/ledger.sqlite")
    p.add_argument("--out", default=None, help="write JSON file (default: stdout)")
    p.set_defaults(fn=cmd_export_refused)

    p = sub.add_parser("ingest-hint", help="record STM/client webhook as PENDING only")
    p.add_argument("--db", default="output/fulfillment/ledger.sqlite")
    p.add_argument("--json-file", required=True)
    p.add_argument("--network", default="testnet11")
    p.add_argument(
        "--webhook-secret",
        default=None,
        help="require payload.shared_secret to match (abuse resistance)",
    )
    p.add_argument(
        "--rate-limit",
        type=int,
        default=None,
        help="max hints accepted per process per 60s window",
    )
    p.set_defaults(fn=cmd_ingest_hint)

    p = sub.add_parser("export-audit", help="export append-only audit log (incident recovery)")
    p.add_argument("--db", default="output/fulfillment/ledger.sqlite")
    p.add_argument("--out", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(fn=cmd_export_audit)

    p = sub.add_parser("backup", help="crash-consistent ledger snapshot + integrity check")
    p.add_argument("--db", default="output/fulfillment/ledger.sqlite")
    p.add_argument("--out", required=True, help="destination .sqlite path")
    p.set_defaults(fn=cmd_backup)

    p = sub.add_parser("lookup", help="support: lookup purchase by payment coin_id")
    p.add_argument("--db", default="output/fulfillment/ledger.sqlite")
    p.add_argument("--coin-id", required=True)
    p.set_defaults(fn=cmd_lookup)

    p = sub.add_parser(
        "archive-fulfilled",
        help="export (and optionally delete) old fulfilled purchase rows",
    )
    p.add_argument("--db", default="output/fulfillment/ledger.sqlite")
    p.add_argument("--days", type=int, default=30, help="age cutoff in days")
    p.add_argument("--out", required=True, help="JSON archive path")
    p.add_argument(
        "--apply",
        action="store_true",
        help="write archive and delete rows (default is dry-run count only)",
    )
    p.set_defaults(fn=cmd_archive_fulfilled)

    p = sub.add_parser("reconcile", help="cron entrypoint: poll source + fulfill (N loops)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--fixture", help="JSON array of confirmed purchases")
    src.add_argument("--coinset-url", help="base URL for CoinsetPollingSource")
    p.add_argument("--salt-file", required=True)
    p.add_argument("--db", default="output/fulfillment/ledger.sqlite")
    p.add_argument("--network", default="testnet11", choices=["testnet11", "mainnet"])
    p.add_argument("--strategy", default="claim", choices=["claim", "stm"])
    p.add_argument("--manifest-outdir", default="output/fulfillment/chests")
    p.add_argument("--metadata-outdir", default="output/fulfillment/metadata")
    p.add_argument(
        "--reveal-outdir",
        default=None,
        help="publish fulfilled chest JSON for reveal.html ?offer=",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--allow-mainnet",
        action="store_true",
        help="required with --network mainnet for live (non-dry-run) fulfill",
    )
    p.add_argument("--loops", type=int, default=1, help="reconcile cycles (default 1)")
    p.add_argument("--interval", type=float, default=0.0, help="seconds between loops")
    p.add_argument(
        "--lock-file",
        default=None,
        help="exclusive reconcile lock path (default: <db>.lock)",
    )
    p.add_argument(
        "--lock-stale-s",
        type=float,
        default=3600.0,
        help="break lock if older than this many seconds",
    )
    p.set_defaults(fn=cmd_reconcile)

    args = ap.parse_args()
    configure_logging(json_logs=bool(getattr(args, "log_json", False)))
    # Refuse live mainnet fulfillment until go-live is an explicit opt-in.
    # Covers tick + reconcile (cron); dry-run still allowed for dress rehearsals.
    write_cmds = {"tick", "reconcile"}
    if (
        args.cmd in write_cmds
        and getattr(args, "network", None) == "mainnet"
        and not getattr(args, "dry_run", False)
        and not getattr(args, "allow_mainnet", False)
    ):
        log.error(
            "refusing mainnet %s without --dry-run or --allow-mainnet "
            "(go-live flag; default is testnet-first)",
            args.cmd,
        )
        return 2
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
