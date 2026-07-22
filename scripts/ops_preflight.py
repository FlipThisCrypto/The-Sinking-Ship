# SPDX-License-Identifier: MIT
"""Operator preflight: validate environment before a mint tick / reconcile.

Checks configs, salt entropy floor, ledger integrity (if present), sprites,
and optional coinset reachability — fail closed with non-zero exit.

Usage:
    python scripts/ops_preflight.py --salt-file secrets/test.salt
    python scripts/ops_preflight.py --salt-file s.salt --db output/f/ledger.sqlite
    python scripts/ops_preflight.py --salt-file s.salt --coinset-url http://127.0.0.1:9
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))


def check(name: str, ok: bool, detail: str, errors: list, warnings: list) -> dict:
    row = {"check": name, "ok": ok, "detail": detail}
    if not ok:
        errors.append(row)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salt-file", required=True)
    ap.add_argument("--db", default=None, help="optional ledger path to integrity-check")
    ap.add_argument("--coinset-url", default=None, help="optional base URL /height probe")
    ap.add_argument("--skip-sprites", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    from shipgen.config import GenConfig
    from render_engine import Palette, load_profile, validate_sprites
    from fulfillment.ledger import SqliteLedger

    results: list[dict] = []
    errors: list[dict] = []
    warnings: list[dict] = []

    # Configs
    try:
        cfg = GenConfig()
        results.append(check(
            "configs", True,
            f"bundle {cfg.config_hash[:16]}… tiers={len(cfg.tiers)}",
            errors, warnings,
        ))
    except Exception as e:
        results.append(check("configs", False, str(e), errors, warnings))
        cfg = None

    # Chain identity (OPS-1): DID, royalty address, collection id must be real
    # before any mint — a placeholder here would mint under the wrong identity.
    try:
        from shipgen.config import load_json as _load_json
        from shipgen.identity import check_chain_identity
        coll = _load_json(ROOT / "config" / "collection.json")
        problems = check_chain_identity(coll)
        results.append(check(
            "chain_identity", not problems,
            "ok (DID, royalty, collection id set)" if not problems
            else "; ".join(problems),
            errors, warnings,
        ))
    except Exception as e:
        results.append(check("chain_identity", False, str(e), errors, warnings))

    # Salt
    salt_path = Path(args.salt_file)
    if not salt_path.is_file():
        results.append(check("salt", False, f"missing {salt_path}", errors, warnings))
    else:
        data = salt_path.read_bytes().strip()
        if len(data) < 16:
            results.append(check(
                "salt", False, f"only {len(data)} bytes (need >= 16)", errors, warnings,
            ))
        else:
            results.append(check("salt", True, f"{len(data)} bytes", errors, warnings))

    # Sprites
    if not args.skip_sprites and cfg is not None:
        try:
            profile = load_profile(None)
            n_err = validate_sprites(cfg, Palette(), profile, ROOT / "sprites")
            results.append(check(
                "sprites", n_err == 0, f"errors={n_err}", errors, warnings,
            ))
        except Exception as e:
            results.append(check("sprites", False, str(e), errors, warnings))

    # Ledger optional
    if args.db:
        db = Path(args.db)
        if not db.is_file():
            results.append(check("ledger", False, f"missing {db}", errors, warnings))
        elif cfg is not None:
            caps = {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}
            led = SqliteLedger(db, caps)
            try:
                ok = led.integrity_ok()
                s = led.status_summary()
                results.append(check(
                    "ledger", ok,
                    f"integrity_ok={ok} purchases={s['total_purchases']}",
                    errors, warnings,
                ))
            finally:
                led.close()

    # Coinset optional probe
    if args.coinset_url:
        url = args.coinset_url.rstrip("/") + "/height"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            h = body.get("height")
            results.append(check(
                "coinset", isinstance(h, int), f"height={h}", errors, warnings,
            ))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as e:
            results.append(check("coinset", False, str(e), errors, warnings))

    report = {
        "ok": len(errors) == 0,
        "checks": results,
        "error_count": len(errors),
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
