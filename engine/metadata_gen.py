# SPDX-License-Identifier: MIT
"""CHIP-0007 metadata generator (P6).

Consumes chest manifests from chest_roller.py and emits one strict
CHIP-0007 JSON per *generated* NFT (grails are hand-authored 1/1s and are
reported, not generated). Deterministic: the same manifest always produces
byte-identical metadata files.

Design notes (ADR-0001 C5): strict CHIP-0007 — format, series_number/
series_total, full collection block — so no downstream consumer ever needs
the four-way token-id fallback heuristics the reference repo was forced
into. rarity_tier / depth_zone / provenance_hash ride in `attributes` per
prompt P6. Optional layers rolled as "None" are omitted from attributes
(marketplace convention); pose is included since it is a visible trait.

Usage:
    python engine/metadata_gen.py --manifest output/chests/<f>.json --outdir output/metadata
    python engine/metadata_gen.py --batch output/chests --outdir output/metadata
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

from shipgen.config import GenConfig, load_json, CONFIG_DIR
from shipgen.schema import validate, SchemaError

log = logging.getLogger("metadata_gen")

NAME_FMT = "Sinking Ship #{:05d}"


class MetadataGenerator:
    def __init__(self, config_dir: Path = CONFIG_DIR):
        self.cfg = GenConfig(config_dir)
        self.collection_doc = load_json(config_dir / "collection.json")
        validate(self.collection_doc,
                 load_json(config_dir / "schemas" / "collection.schema.json"))
        self.descriptions = load_json(config_dir / "descriptions.json")
        validate(self.descriptions,
                 load_json(config_dir / "schemas" / "descriptions.schema.json"))
        self.chip_schema = load_json(config_dir / "schemas" / "chip0007.schema.json")
        self._collection_block = self._build_collection_block()

    def _build_collection_block(self) -> dict:
        c = self.collection_doc["collection"]
        m = self.collection_doc["minting"]
        return {
            "id": c["id"],
            "name": c["name"],
            "attributes": [
                {"type": "description", "value": c["description"]},
                {"type": "icon", "value": c["icon"]},
                {"type": "banner", "value": c["banner"]},
                {"type": "twitter", "value": c["twitter"]},
                {"type": "website", "value": c["website"]},
                {"type": "license", "value": c["license_url"]},
                {"type": "royalty_percentage_basis_points",
                 "value": str(m["royalty_percentage_basis_points"])},
            ],
        }

    def _description_for(self, zone: str, coin_id: str, global_index: int) -> str:
        lines = self.descriptions["lines"][zone]
        h = int(hashlib.sha256(f"desc:{coin_id}:{global_index}".encode()).hexdigest(), 16)
        return lines[h % len(lines)]

    def nft_metadata(self, manifest: dict, entry: dict) -> dict:
        if entry["type"] != "generated":
            raise ValueError("grail entries are hand-authored, not generated")
        zone = manifest["zone"]
        tier = self.cfg.tiers[manifest["tier"]]
        attributes = []
        for layer_name in self.cfg.roll_order:
            layer = self.cfg.layer_by_name[layer_name]
            value = entry["traits"].get(layer_name)
            if value is None or value == "None":
                continue
            if value == "The Torn":
                attributes.append({"trait_type": layer.display_name,
                                   "value": "Halo + Horns (The Torn)"})
            else:
                attributes.append({"trait_type": layer.display_name, "value": value})
        attributes.sort(key=lambda a: a["trait_type"])
        attributes += [
            {"trait_type": "rarity_tier", "value": entry["rarity_tier"]},
            {"trait_type": "depth_zone", "value": zone},
            {"trait_type": "dive_tier", "value": tier["display_name"]},
            {"trait_type": "provenance_hash", "value": manifest["provenance_commitment"]},
        ]
        doc = {
            "format": "CHIP-0007",
            "name": NAME_FMT.format(entry["global_index"]),
            "description": self._description_for(zone, manifest["coin_id"],
                                                 entry["global_index"]),
            "minting_tool": self.collection_doc["minting"]["minting_tool"],
            "sensitive_content": False,
            "series_number": entry["global_index"],
            "series_total": self.collection_doc["minting"]["series_total"],
            "license": self.collection_doc["collection"]["license_url"],
            "attributes": attributes,
            "collection": self._collection_block,
        }
        validate(doc, self.chip_schema)
        return doc

    def process_manifest(self, manifest_path: Path, outdir: Path,
                         dry_run: bool = False) -> tuple[int, int]:
        manifest = load_json(manifest_path)
        if manifest.get("schema") != "chest-manifest-v1":
            raise ValueError(f"{manifest_path} is not a chest-manifest-v1 file")
        if manifest.get("config_version_hash") != self.cfg.config_hash:
            log.warning("%s was rolled with config hash %.12s… but local configs "
                        "give %.12s… — metadata reflects LOCAL display names",
                        manifest_path.name, manifest.get("config_version_hash", ""),
                        self.cfg.config_hash)
        written = grails = 0
        outdir.mkdir(parents=True, exist_ok=True)
        for entry in manifest["nfts"]:
            if entry["type"] == "grail":
                grails += 1
                log.info("  slot %d: GRAIL #%d — hand-authored metadata required",
                         entry["slot"], entry["grail_number"])
                continue
            doc = self.nft_metadata(manifest, entry)
            path = outdir / f"{entry['global_index']:05d}.json"
            if not dry_run:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(doc, f, indent=2, ensure_ascii=False)
                    f.write("\n")
            written += 1
        return written, grails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--manifest", metavar="FILE", help="one chest manifest")
    src.add_argument("--batch", metavar="DIR", help="process every chest_*.json in DIR")
    ap.add_argument("--outdir", default="output/metadata")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate and report without writing files")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    gen = MetadataGenerator()
    outdir = Path(args.outdir)
    paths = ([Path(args.manifest)] if args.manifest
             else sorted(Path(args.batch).glob("chest_*.json")))
    if not paths:
        log.error("no chest manifests found")
        return 1

    total = total_grails = 0
    for p in paths:
        try:
            written, grails = gen.process_manifest(p, outdir, args.dry_run)
        except (ValueError, SchemaError) as e:
            log.error("%s: %s", p, e)
            return 1
        log.info("%s: %d metadata file(s)%s%s", p.name, written,
                 f", {grails} grail(s) skipped" if grails else "",
                 " [dry-run]" if args.dry_run else "")
        total += written
        total_grails += grails
    log.info("done: %d CHIP-0007 file(s) -> %s (%d grail slots need hand-authored metadata)",
             total, outdir, total_grails)
    return 0


if __name__ == "__main__":
    sys.exit(main())
