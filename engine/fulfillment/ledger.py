# SPDX-License-Identifier: MIT
"""SQLite fulfillment ledger — UNIQUE(coin_id), crash-resume, supply accounting."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .types import FulfillmentLedger, PaymentState, TierPurchase


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SqliteLedger(FulfillmentLedger):
    """Transactional ledger. All mutations are atomic per connection method."""

    def __init__(self, path: str | Path, tier_pass_caps: dict[str, int]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tier_pass_caps = dict(tier_pass_caps)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        # Wait up to 5s on lock contention (concurrent tick / status / export).
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    # ---------------------------------------------------------------------------
    # Versioned migration framework.  Add new entries to _MIGRATIONS to make
    # forward-compatible schema changes.  Migrations run in version order and
    # are each wrapped in an IMMEDIATE transaction so a partial upgrade on crash
    # is rolled back automatically.  Schema version 0 is the pre-meta state;
    # version 1 is the initial full schema.  New migrations start at version 2.
    # ---------------------------------------------------------------------------
    _MIGRATIONS: dict[int, str] = {
        # v1 → v2: add archived_at for retention archiving (retention.py).
        # Using ALTER TABLE ADD COLUMN (SQLite supports nullable / defaulted
        # additions without table reconstruction).
        2: "ALTER TABLE purchases ADD COLUMN archived_at TEXT",
    }
    # Highest known version after applying all migrations.
    _SCHEMA_TARGET: int = max(_MIGRATIONS) if _MIGRATIONS else 1

    def _migrate(self) -> None:
        # Phase 1: create baseline schema (idempotent CREATE IF NOT EXISTS).
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tier_counters (
                tier_name TEXT PRIMARY KEY,
                next_ordinal INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS purchases (
                coin_id TEXT PRIMARY KEY,
                tier_name TEXT NOT NULL,
                pass_ordinal INTEGER NOT NULL,
                start_index INTEGER,
                buyer_address TEXT NOT NULL,
                block_height INTEGER NOT NULL,
                network TEXT NOT NULL,
                state TEXT NOT NULL,
                quantity INTEGER,
                generated_count INTEGER,
                manifest_json TEXT,
                manifest_hash TEXT,
                offer_id TEXT,
                refuse_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id TEXT,
                action TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_purchases_state ON purchases(state);
            """
        )
        # Phase 2: seed required meta keys.
        for key, default in (
            ("next_start_index", "1"),
            ("schema_version", "1"),
            ("last_polled_height", "0"),
        ):
            if self._conn.execute(
                "SELECT 1 FROM meta WHERE key = ?", (key,)
            ).fetchone() is None:
                self._conn.execute(
                    "INSERT INTO meta(key, value) VALUES (?, ?)", (key, default)
                )
        # Phase 3: apply any pending versioned migrations in order.
        current = int(self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()[0])
        for version in sorted(self._MIGRATIONS):
            if version <= current:
                continue
            sql = self._MIGRATIONS[version]
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(sql)
                self._conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                    (str(version),),
                )
                self._conn.execute("COMMIT")
                current = version
            except Exception:
                self._conn.execute("ROLLBACK")
                raise



    def _audit(self, coin_id: str | None, action: str, detail: dict | None = None) -> None:
        self._conn.execute(
            "INSERT INTO audit(coin_id, action, detail, created_at) VALUES (?,?,?,?)",
            (coin_id, action, json.dumps(detail or {}, sort_keys=True), _utc_now()),
        )

    def _meta_get(self, key: str) -> str:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"]

    def _meta_set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def record_pending_hint(self, p: TierPurchase) -> None:
        """Untrusted client/webhook hint → PENDING only. No ordinal, no roll."""
        existing = self._conn.execute(
            "SELECT state FROM purchases WHERE coin_id = ?", (p.coin_id,)
        ).fetchone()
        if existing is not None:
            return  # already tracked; never downgrade
        if p.tier_name not in self.tier_pass_caps:
            raise ValueError(f"unknown tier {p.tier_name!r}")
        now = _utc_now()
        self._conn.execute(
            "INSERT INTO purchases("
            "coin_id, tier_name, pass_ordinal, start_index, buyer_address, "
            "block_height, network, state, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (p.coin_id, p.tier_name, 0, None, p.buyer_address,
             p.block_height, p.network, PaymentState.PENDING.value, now, now),
        )
        self._audit(p.coin_id, "record_pending_hint", {
            "tier": p.tier_name, "block_height": p.block_height,
        })

    def record_purchase(self, p: TierPurchase) -> int:
        existing = self._conn.execute(
            "SELECT pass_ordinal, state FROM purchases WHERE coin_id = ?",
            (p.coin_id,),
        ).fetchone()
        if existing is not None and existing["state"] != PaymentState.PENDING.value:
            return int(existing["pass_ordinal"])

        cap = self.tier_pass_caps.get(p.tier_name)
        if cap is None:
            raise ValueError(f"unknown tier {p.tier_name!r}")

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            # re-check under lock
            existing = self._conn.execute(
                "SELECT pass_ordinal, state FROM purchases WHERE coin_id = ?",
                (p.coin_id,),
            ).fetchone()
            if existing is not None and existing["state"] != PaymentState.PENDING.value:
                self._conn.execute("COMMIT")
                return int(existing["pass_ordinal"])

            row = self._conn.execute(
                "SELECT next_ordinal FROM tier_counters WHERE tier_name = ?",
                (p.tier_name,),
            ).fetchone()
            ordinal = int(row["next_ordinal"]) if row else 1
            if ordinal > cap:
                self._conn.execute("COMMIT")
                raise ValueError(
                    f"tier {p.tier_name} is sold out (cap {cap})")

            now = _utc_now()
            if existing is not None and existing["state"] == PaymentState.PENDING.value:
                self._conn.execute(
                    "UPDATE purchases SET pass_ordinal = ?, buyer_address = ?, "
                    "block_height = ?, network = ?, state = ?, updated_at = ? "
                    "WHERE coin_id = ?",
                    (ordinal, p.buyer_address, p.block_height, p.network,
                     PaymentState.CONFIRMED.value, now, p.coin_id),
                )
                action = "promote_pending_to_confirmed"
            else:
                self._conn.execute(
                    "INSERT INTO purchases("
                    "coin_id, tier_name, pass_ordinal, start_index, buyer_address, "
                    "block_height, network, state, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (p.coin_id, p.tier_name, ordinal, None, p.buyer_address,
                     p.block_height, p.network, PaymentState.CONFIRMED.value, now, now),
                )
                action = "record_purchase"
            self._conn.execute(
                "INSERT INTO tier_counters(tier_name, next_ordinal) VALUES (?, ?) "
                "ON CONFLICT(tier_name) DO UPDATE SET next_ordinal = excluded.next_ordinal",
                (p.tier_name, ordinal + 1),
            )
            self._audit(p.coin_id, action, {
                "tier": p.tier_name, "pass_ordinal": ordinal,
                "block_height": p.block_height,
            })
            self._conn.execute("COMMIT")
            return ordinal
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def state_of(self, coin_id: str) -> PaymentState | None:
        row = self._conn.execute(
            "SELECT state FROM purchases WHERE coin_id = ?", (coin_id,)
        ).fetchone()
        return PaymentState(row["state"]) if row else None

    def peek_next_start_index(self) -> int:
        return int(self._meta_get("next_start_index"))

    def save_roll(self, coin_id: str, manifest: dict, dry_run: bool = False) -> None:
        if dry_run:
            self._audit(coin_id, "save_roll_dry_run", {
                "manifest_hash": manifest.get("manifest_hash"),
                "quantity": manifest.get("quantity"),
            })
            return
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT state, manifest_json, start_index FROM purchases WHERE coin_id = ?",
                (coin_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown coin_id {coin_id}")
            if row["manifest_json"]:
                # already rolled — resume must not re-roll or re-advance
                self._conn.execute("COMMIT")
                return
            if row["state"] not in (PaymentState.CONFIRMED.value, PaymentState.ROLLED.value):
                raise ValueError(f"cannot roll purchase in state {row['state']}")

            start = int(self._meta_get("next_start_index"))
            if manifest.get("start_index") != start:
                raise ValueError(
                    f"manifest start_index {manifest.get('start_index')} != "
                    f"ledger next {start} — refuse non-deterministic advance")
            gen = int(manifest["generated_count"])
            qty = int(manifest["quantity"])
            now = _utc_now()
            self._conn.execute(
                "UPDATE purchases SET start_index = ?, quantity = ?, "
                "generated_count = ?, manifest_json = ?, manifest_hash = ?, "
                "state = ?, updated_at = ? WHERE coin_id = ?",
                (start, qty, gen, json.dumps(manifest, sort_keys=True),
                 manifest["manifest_hash"], PaymentState.ROLLED.value, now, coin_id),
            )
            self._meta_set("next_start_index", str(start + gen))
            self._audit(coin_id, "save_roll", {
                "manifest_hash": manifest["manifest_hash"],
                "start_index": start,
                "generated_count": gen,
                "quantity": qty,
            })
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def get_manifest(self, coin_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT manifest_json FROM purchases WHERE coin_id = ?", (coin_id,)
        ).fetchone()
        if not row or not row["manifest_json"]:
            return None
        return json.loads(row["manifest_json"])

    def mark_fulfilled(self, coin_id: str, manifest_hash: str,
                       offer_id: str, dry_run: bool = False) -> None:
        if dry_run:
            self._audit(coin_id, "mark_fulfilled_dry_run", {
                "manifest_hash": manifest_hash, "offer_id": offer_id,
            })
            return
        now = _utc_now()
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT state, manifest_hash FROM purchases WHERE coin_id = ?",
                (coin_id,),
            ).fetchone()
            if row is None:
                raise KeyError(coin_id)
            if row["state"] == PaymentState.FULFILLED.value:
                self._conn.execute("COMMIT")
                return  # idempotent
            if row["state"] != PaymentState.ROLLED.value:
                raise ValueError(f"fulfill requires ROLLED, got {row['state']}")
            if row["manifest_hash"] != manifest_hash:
                raise ValueError("manifest_hash mismatch at fulfill")
            self._conn.execute(
                "UPDATE purchases SET state = ?, offer_id = ?, updated_at = ? "
                "WHERE coin_id = ?",
                (PaymentState.FULFILLED.value, offer_id, now, coin_id),
            )
            self._audit(coin_id, "mark_fulfilled", {
                "manifest_hash": manifest_hash, "offer_id": offer_id,
            })
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def mark_refused(self, coin_id: str, reason: str, dry_run: bool = False) -> None:
        if dry_run:
            self._audit(coin_id, "mark_refused_dry_run", {"reason": reason})
            return
        now = _utc_now()
        self._conn.execute(
            "UPDATE purchases SET state = ?, refuse_reason = ?, updated_at = ? "
            "WHERE coin_id = ?",
            (PaymentState.REFUSED.value, reason, now, coin_id),
        )
        self._audit(coin_id, "mark_refused", {"reason": reason})

    def supply_consumed(self) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS n FROM purchases "
            "WHERE state IN (?, ?) AND quantity IS NOT NULL",
            (PaymentState.ROLLED.value, PaymentState.FULFILLED.value),
        ).fetchone()
        return int(row["n"])

    def purchases_needing_work(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT coin_id FROM purchases WHERE state IN (?, ?) ORDER BY created_at",
            (PaymentState.CONFIRMED.value, PaymentState.ROLLED.value),
        ).fetchall()
        return [r["coin_id"] for r in rows]

    def get_row(self, coin_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM purchases WHERE coin_id = ?", (coin_id,)
        ).fetchone()
        return dict(row) if row else None

    def last_polled_height(self) -> int:
        return int(self._meta_get("last_polled_height"))

    def set_last_polled_height(self, height: int) -> None:
        self._meta_set("last_polled_height", str(height))

    def integrity_ok(self) -> bool:
        """SQLite quick integrity check (ops / crash recovery)."""
        row = self._conn.execute("PRAGMA quick_check").fetchone()
        return bool(row) and str(row[0]).lower() == "ok"

    def status_summary(self) -> dict:
        rows = self._conn.execute(
            "SELECT state, COUNT(*) AS n FROM purchases GROUP BY state"
        ).fetchall()
        by_state = {r["state"]: int(r["n"]) for r in rows}
        consumed = self.supply_consumed()
        # public_mint_budget is not stored in the ledger; callers that know
        # GenConfig may enrich. Keep headroom null here for pure ledger view.
        return {
            "by_state": by_state,
            "supply_consumed": consumed,
            "next_start_index": self.peek_next_start_index(),
            "last_polled_height": self.last_polled_height(),
            "total_purchases": sum(by_state.values()),
            "db_path": str(self.path),
            "integrity_ok": self.integrity_ok(),
            "schema_version": int(self._meta_get("schema_version") or "1"),
            "schema_target": self._SCHEMA_TARGET,
        }

    def list_refused(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT coin_id, tier_name, pass_ordinal, buyer_address, "
            "block_height, refuse_reason, updated_at FROM purchases "
            "WHERE state = ? ORDER BY updated_at",
            (PaymentState.REFUSED.value,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_by_state(self, state: PaymentState) -> list[dict]:
        rows = self._conn.execute(
            "SELECT coin_id, tier_name, pass_ordinal, state, "
            "manifest_hash, quantity, updated_at FROM purchases "
            "WHERE state = ? ORDER BY updated_at",
            (state.value,),
        ).fetchall()
        return [dict(r) for r in rows]

    def export_audit(self, limit: int | None = None) -> list[dict]:
        """Append-only audit log, oldest first (ops / incident recovery)."""
        sql = "SELECT id, coin_id, action, detail, created_at FROM audit ORDER BY id"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        rows = self._conn.execute(sql).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("detail"):
                try:
                    d["detail"] = json.loads(d["detail"])
                except json.JSONDecodeError:
                    pass
            out.append(d)
        return out
