# SPDX-License-Identifier: MIT
"""Ledger retention helpers: archive fulfilled rows older than a cutoff.

Mint-window ledgers can grow large; operators may archive completed rows
while keeping audit history. Destructive actions require dry_run=False.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def parse_cutoff_days(days: int) -> str:
    if days < 1:
        raise ValueError("days must be >= 1")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.replace(microsecond=0).isoformat()


def archive_fulfilled(
    db_path: str | Path,
    *,
    older_than_days: int,
    archive_path: str | Path,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Export then optionally delete fulfilled rows older than N days.

    Audit log is retained. Pending/confirmed/rolled/refused are never archived.
    """
    cutoff = parse_cutoff_days(older_than_days)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM purchases WHERE state = 'fulfilled' "
            "AND updated_at < ? ORDER BY updated_at",
            (cutoff,),
        ).fetchall()
        docs = [dict(r) for r in rows]
        report = {
            "cutoff": cutoff,
            "matched": len(docs),
            "dry_run": dry_run,
            "archive_path": str(archive_path),
            "deleted": 0,
        }
        if not docs:
            return report
        Path(archive_path).parent.mkdir(parents=True, exist_ok=True)
        if not dry_run:
            Path(archive_path).write_text(
                json.dumps(docs, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            cur = conn.execute(
                "DELETE FROM purchases WHERE state = 'fulfilled' AND updated_at < ?",
                (cutoff,),
            )
            conn.commit()
            report["deleted"] = cur.rowcount
            conn.execute(
                "INSERT INTO audit(coin_id, action, detail, created_at) VALUES (?,?,?,?)",
                (
                    None,
                    "archive_fulfilled",
                    json.dumps({"matched": len(docs), "deleted": report["deleted"],
                                "cutoff": cutoff}),
                    datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                ),
            )
            conn.commit()
        return report
    finally:
        conn.close()
