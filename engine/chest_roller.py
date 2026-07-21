# SPDX-License-Identifier: MIT
"""Deterministic chest roller: commit / roll / verify (P5, spec 5.4).

commit  — derive the provenance commitment from configs + secret salt.
          Publish ONLY the printed hash pre-mint; the commitment document
          (which contains the salt and all grail/Torn placements) stays
          secret until reveal.
roll    — roll one chest for a paying coin_id. Deterministic: the same
          (salt, coin_id, tier, pass_ordinal, start_index) always produces
          a byte-identical manifest, on any machine.
verify  — recompute a published manifest from the revealed salt and confirm
          it matches bit-for-bit (the post-mint fairness check anyone can run).

Usage:
    python engine/chest_roller.py commit --salt-file secrets/mint.salt
    python engine/chest_roller.py roll --tier submarine_captain \
        --coin-id 0x<64 hex> --salt-file secrets/mint.salt \
        --pass-ordinal 17 --start-index 12345 --outdir output/chests
    python engine/chest_roller.py verify --manifest output/chests/<f>.json \
        --salt-file secrets/mint.salt
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from shipgen.canon import canon_json, hash_obj
from shipgen.config import GenConfig
from shipgen.roll import RollEngine, build_commitment

log = logging.getLogger("chest_roller")

MIN_SALT_BYTES = 16


def read_salt(path: str) -> bytes:
    data = Path(path).read_bytes().strip()
    if not data:
        raise SystemExit(f"salt file {path} is empty")
    if len(data) < MIN_SALT_BYTES:
        raise SystemExit(
            f"salt file {path} is only {len(data)} bytes "
            f"(need >= {MIN_SALT_BYTES} bytes of high entropy)"
        )
    return data


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")


# Required fields on a published chest-manifest-v1 for verification.
_MANIFEST_REQUIRED = (
    "schema", "coin_id", "tier", "pass_ordinal", "start_index",
    "manifest_hash", "provenance_commitment", "config_version_hash", "nfts",
)


def _require_manifest_shape(doc: dict) -> list[str]:
    problems = []
    if not isinstance(doc, dict):
        return ["manifest root must be a JSON object"]
    for key in _MANIFEST_REQUIRED:
        if key not in doc:
            problems.append(f"manifest missing required field {key!r}")
    if doc.get("schema") not in (None, "chest-manifest-v1"):
        problems.append(f"unsupported manifest schema {doc.get('schema')!r}")
    return problems


def cmd_commit(args) -> int:
    salt = read_salt(args.salt_file)
    cfg = GenConfig()
    result = build_commitment(salt, cfg)
    outdir = Path(args.outdir)
    write_json(outdir / "commitment.json", result["commitment"])
    (outdir / "commitment_hash.txt").parent.mkdir(parents=True, exist_ok=True)
    (outdir / "commitment_hash.txt").write_text(
        result["commitment_hash"] + "\n", encoding="ascii", newline="\n")
    log.info("config bundle hash : %s", cfg.config_hash)
    log.info("commitment written : %s  (SECRET until reveal — contains salt "
             "+ grail/Torn placements)", outdir / "commitment.json")
    log.info("PUBLISH THIS HASH  : %s", result["commitment_hash"])
    return 0


def cmd_roll(args) -> int:
    salt = read_salt(args.salt_file)
    cfg = GenConfig()
    engine = RollEngine(cfg)
    commitment = build_commitment(salt, cfg)
    try:
        manifest = engine.roll_chest(
            salt, args.coin_id, args.tier, args.pass_ordinal, args.start_index,
            commitment["commitment"]["placements"], commitment["commitment_hash"])
    except (ValueError, RuntimeError) as e:
        log.error("roll failed: %s", e)
        return 1
    coin8 = manifest["coin_id"][:8]
    out = Path(args.outdir) / f"chest_{args.tier}_{coin8}.json"
    if args.dry_run:
        log.info("[dry-run] would write %s", out)
    else:
        write_json(out, manifest)
        log.info("manifest written: %s", out)
    log.info("tier=%s quantity=%d generated=%d grails=%d torn=%d pity=%s",
             manifest["tier"], manifest["quantity"], manifest["generated_count"],
             manifest["quantity"] - manifest["generated_count"],
             len(manifest["the_torn_indices"]), manifest["pity_upgraded_slots"] or "-")
    log.info("manifest hash: %s", manifest["manifest_hash"])
    tiers = {}
    for e in manifest["nfts"]:
        key = "grail" if e["type"] == "grail" else e["rarity_tier"]
        tiers[key] = tiers.get(key, 0) + 1
    log.info("contents: %s", ", ".join(f"{k}:{v}" for k, v in sorted(tiers.items())))
    return 0


def cmd_verify(args) -> int:
    salt = read_salt(args.salt_file)
    cfg = GenConfig()
    engine = RollEngine(cfg)
    try:
        with open(args.manifest, encoding="utf-8") as f:
            published = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log.error("FAIL: cannot read manifest %s: %s", args.manifest, e)
        return 1

    problems = _require_manifest_shape(published)
    if problems:
        for p in problems:
            log.error("FAIL: %s", p)
        return 1

    commitment = build_commitment(salt, cfg)
    if published.get("config_version_hash") != cfg.config_hash:
        problems.append(
            f"config hash mismatch: manifest has {published.get('config_version_hash')!r}, "
            f"local configs give {cfg.config_hash!r} — verify against the revealed configs")
    if published.get("provenance_commitment") != commitment["commitment_hash"]:
        problems.append("provenance commitment mismatch: this salt does not produce the "
                        "committed hash embedded in the manifest")

    try:
        recomputed = engine.roll_chest(
            salt, published["coin_id"], published["tier"], published["pass_ordinal"],
            published["start_index"], commitment["commitment"]["placements"],
            commitment["commitment_hash"])
    except (ValueError, RuntimeError, KeyError, TypeError) as e:
        problems.append(f"cannot recompute chest from published fields: {e}")
        for p in problems:
            log.error("FAIL: %s", p)
        return 1

    if canon_json(recomputed) != canon_json(published):
        problems.append("recomputed manifest differs from the published manifest")
        body = {k: v for k, v in published.items() if k != "manifest_hash"}
        if hash_obj(body) != published.get("manifest_hash"):
            problems.append("published manifest_hash does not even match its own body "
                            "(file was edited)")
    if problems:
        for p in problems:
            log.error("FAIL: %s", p)
        return 1
    log.info("VERIFIED: manifest %s reproduces exactly from salt + coin_id "
             "(hash %s)", args.manifest, published["manifest_hash"])
    return 0


def main() -> int:
    from shipgen import __version__ as shipgen_version

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--version",
        action="version",
        version=f"chest_roller {shipgen_version} (shipgen {shipgen_version})",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("commit", help="build the provenance commitment")
    p.add_argument("--salt-file", required=True)
    p.add_argument("--outdir", default="output/commitment")
    p.set_defaults(fn=cmd_commit)

    p = sub.add_parser("roll", help="roll one chest deterministically")
    p.add_argument("--tier", required=True)
    p.add_argument("--coin-id", required=True, help="payment coin id (64 hex chars)")
    p.add_argument("--salt-file", required=True)
    p.add_argument("--pass-ordinal", type=int, required=True,
                   help="1-based purchase sequence within the tier (from the mint ledger)")
    p.add_argument("--start-index", type=int, required=True,
                   help="global generated-NFT counter at fulfillment time (from the ledger); "
                        "must be >= 1")
    p.add_argument("--outdir", default="output/chests")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_roll)

    p = sub.add_parser("verify", help="recompute and confirm a published chest")
    p.add_argument("--manifest", required=True)
    p.add_argument("--salt-file", required=True)
    p.set_defaults(fn=cmd_verify)

    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        return args.fn(args)
    except (OSError, ValueError, RuntimeError) as e:
        log.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
