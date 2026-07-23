# SPDX-License-Identifier: MIT
"""Round 2 Iteration 2: tests for versioned ledger migration framework."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fulfillment.ledger import SqliteLedger


CAPS = {"castaway": 10}


def _new_ledger(tmp_path: Path) -> SqliteLedger:
    return SqliteLedger(tmp_path / "ledger.sqlite", CAPS)


def test_new_db_migrates_to_schema_target(tmp_path):
    """A brand-new ledger must open at the schema_target version."""
    led = _new_ledger(tmp_path)
    status = led.status_summary()
    led.close()
    assert status["schema_version"] == led._SCHEMA_TARGET
    assert status["schema_version"] >= 2


def test_schema_version_in_meta_table(tmp_path):
    """Schema version persists in the meta table across connections."""
    led = _new_ledger(tmp_path)
    db_path = led.path
    led.close()

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert int(row[0]) >= 2


def test_migration_v2_adds_archived_at_column(tmp_path):
    """v2 migration must add archived_at column to purchases."""
    led = _new_ledger(tmp_path)
    db_path = led.path
    led.close()

    conn = sqlite3.connect(str(db_path))
    pragma = conn.execute("PRAGMA table_info(purchases)").fetchall()
    conn.close()
    columns = {row[1] for row in pragma}
    assert "archived_at" in columns, (
        "v2 migration must add archived_at column; got columns: " + str(columns)
    )


def test_migration_is_idempotent_on_reopen(tmp_path):
    """Re-opening an already-migrated DB must not error or re-run migrations."""
    led1 = _new_ledger(tmp_path)
    v1 = led1.status_summary()["schema_version"]
    led1.close()

    # Second open — migrations already applied; should open cleanly.
    led2 = _new_ledger(tmp_path)
    v2 = led2.status_summary()["schema_version"]
    led2.close()

    assert v1 == v2 == SqliteLedger._SCHEMA_TARGET


def test_old_db_without_archived_at_is_upgraded(tmp_path):
    """Simulate a v1 DB (no archived_at column) and verify v2 migration applies."""
    db_path = tmp_path / "old.sqlite"
    # Build a minimal v1 DB by hand (no archived_at, schema_version=1).
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE tier_counters (tier_name TEXT PRIMARY KEY, next_ordinal INTEGER NOT NULL);
        CREATE TABLE purchases (
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
        CREATE TABLE audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coin_id TEXT,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        );
        INSERT INTO meta VALUES ('schema_version', '1');
        INSERT INTO meta VALUES ('next_start_index', '1');
        INSERT INTO meta VALUES ('last_polled_height', '0');
    """)
    conn.close()

    # Opening via SqliteLedger should auto-apply v2 migration.
    led = SqliteLedger(db_path, CAPS)
    status = led.status_summary()
    led.close()

    assert status["schema_version"] == SqliteLedger._SCHEMA_TARGET

    # Verify archived_at now exists.
    conn = sqlite3.connect(str(db_path))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(purchases)").fetchall()}
    conn.close()
    assert "archived_at" in cols
