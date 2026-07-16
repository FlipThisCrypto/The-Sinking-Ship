# SPDX-License-Identifier: MIT
"""Generate 44 hand-authored grail metadata *stubs* (CHIP-0007 shells).

These are NOT final 1/1 art/lore — they reserve series numbers and structure
so P6 metadata pipeline and marketplace dry-runs can proceed. Replace fields
when the Lore Bible names each grail.

Usage:
    python scripts/gen_grail_stubs.py
    python scripts/gen_grail_stubs.py --outdir output/grail_stubs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from shipgen.config import GenConfig, load_json, CONFIG_DIR  # noqa: E402

# 11 themed sets × 4 (spec 4.3) — display names are placeholders until P1 fills bios.
GRAIL_SETS = [
    ("The Four Admirals", ["Admiral of the Surface", "Admiral of Twilight",
                           "Admiral of Midnight", "Admiral of the Hadal"]),
    ("The Four Wizards of the Deep", ["Wizard of Green Tide", "Wizard of Void Ink",
                                      "Wizard of Crystal Moon", "Wizard of the Offer"]),
    ("The Four Horsemen of the Bear", ["Horseman of Despair", "Horseman of Doubt",
                                       "Horseman of Silence", "Horseman of Exit Liquidity"]),
    ("The Lighthouse Keepers", ["Keeper of the Broken Pier", "Keeper of Storm Harbor",
                                "Keeper of the Graveyard", "Keeper of Dry Dock"]),
    ("The First Divers", ["First Snorkeler", "First Scuba", "First Deep Sea",
                          "First Salvage"]),
    ("The Last Men Aboard", ["Last at the Helm", "Last in the Hold",
                             "Last on the Mast", "Last to Leave"]),
    ("The Shipwrights", ["Keelwright", "Plankwright", "Sparwright", "Spellwright"]),
    ("The Ghost Captains", ["Captain of Fog", "Captain of Bones",
                            "Captain of Silence", "Captain of the Black Flag"]),
    ("The Torn", ["Torn Halo I", "Torn Halo II", "Torn Horns I", "Torn Horns II"]),
    ("The Salvage Kings", ["King of the Surface Haul", "King of the Twilight Haul",
                           "King of the Abyssal Haul", "King of the Hadal Haul"]),
    ("The Ark Builders", ["Builder of the Frame", "Builder of the Hull",
                          "Builder of the Mast", "Builder of the Light"]),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", default="output/grail_stubs")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    cfg = GenConfig()
    collection = load_json(CONFIG_DIR / "collection.json")
    c = collection["collection"]
    m = collection["minting"]
    grail_count = int(cfg.supply["grail_count"])
    assert grail_count == 44

    n = 0
    index = []
    for set_name, members in GRAIL_SETS:
        for member in members:
            n += 1
            # Grail series numbers use a reserved high band documentation-only;
            # on-chain assignment is by grail_number 1..44 in chest manifests.
            doc = {
                "format": "CHIP-0007",
                "name": f"Sinking Ship Grail #{n:02d} — {member}",
                "description": (
                    f"Hand-crafted 1/1. Set: {set_name}. "
                    f"Placeholder bio — replace from Lore Bible (P1). "
                    f"Hope never sinks."
                ),
                "minting_tool": m["minting_tool"],
                "sensitive_content": False,
                "series_number": n,  # stub; live mint maps grail_number → final metadata
                "series_total": m["series_total"],
                "license": c["license_url"],
                "attributes": [
                    {"trait_type": "rarity_tier", "value": "grail"},
                    {"trait_type": "grail_number", "value": str(n)},
                    {"trait_type": "grail_set", "value": set_name},
                    {"trait_type": "grail_name", "value": member},
                    {"trait_type": "stub", "value": "true"},
                ],
                "collection": {
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
                },
            }
            path = outdir / f"grail_{n:02d}.json"
            path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")
            index.append({"grail_number": n, "set": set_name, "name": member,
                          "file": path.name})

    (outdir / "index.json").write_text(
        json.dumps({"count": n, "grails": index}, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    print(f"wrote {n} grail stubs + index -> {outdir}")
    return 0 if n == 44 else 1


if __name__ == "__main__":
    sys.exit(main())
