# SPDX-License-Identifier: MIT
"""Generate PLACEHOLDER sprites + per-layer READMEs from traits.json (P4).

Every sprite required by traits.json is emitted as a clearly-artificial
48x48 placeholder: solid palette-compliant fills in a per-layer region with
a deterministic accent stripe + checker notch so different traits are
visually distinguishable and obviously not final art. Alpha is strictly
0/255 and every color comes from the master palette, so the sprite tree
passes `render_engine.py --validate-sprites` cleanly.

Spec note: masters are 48x48 (the prompt's "8x8 placeholder" instruction
would fail the engine's own dimension validation — flagged as OQ-6).

Usage:
    python scripts/gen_placeholder_sprites.py [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from shipgen.config import GenConfig, load_json, CONFIG_DIR  # noqa: E402

log = logging.getLogger("gen_placeholder_sprites")
ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "sprites"
PX = 48

# (x0, y0, x1, y1) inclusive regions per layer, composed bottom-to-top
REGIONS = {
    "sky": (0, 0, 47, 47),
    "sea": (0, 30, 47, 47),
    "scene_element": (2, 14, 10, 34),
    "ship_class": (12, 22, 39, 34),
    "ship_condition": (12, 18, 39, 23),
    "body": (18, 10, 31, 33),
    "clothing": (18, 26, 31, 33),
    "eyes": (21, 14, 28, 17),
    "mouth": (22, 20, 27, 22),
    "hat": (17, 6, 32, 11),
    "aura": (1, 1, 46, 46),
}


def color_pair(key: str, master: list[tuple[int, int, int]]):
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return master[h % 32], master[(h // 32) % 32]


def draw_placeholder(layer: str, key: str, master) -> Image.Image:
    img = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    px = img.load()
    primary, accent = color_pair(key, master)
    x0, y0, x1, y1 = REGIONS[layer]

    if layer == "aura":
        # dotted ring outline only — top layer must not cover the character
        for x in range(x0, x1 + 1):
            if x % 3 != 2:
                px[x, y0] = (*primary, 255)
                px[x, y1] = (*primary, 255)
        for y in range(y0, y1 + 1):
            if y % 3 != 2:
                px[x0, y] = (*primary, 255)
                px[x1, y] = (*primary, 255)
    else:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[x, y] = (*primary, 255)
        # accent stripe (distinguishes traits sharing a primary color)
        stripe_y = y0 + (int(hashlib.sha256((key + "/s").encode()).hexdigest(), 16)
                         % max(1, y1 - y0))
        for x in range(x0, x1 + 1):
            px[x, stripe_y] = (*accent, 255)

    # 3-px checker notch at region top-left: the "this is a placeholder" mark
    for i in range(3):
        if (x0 + i) <= x1:
            px[x0 + i, y0] = (*(accent if i % 2 == 0 else primary), 255)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = GenConfig()
    palette = load_json(CONFIG_DIR / "palette.json")
    master = [tuple(int(c["hex"][i:i + 2], 16) for i in (1, 3, 5)) for c in palette["master"]]

    written = skipped = 0
    for layer in cfg.layers:
        if layer.rendered_via:
            continue
        ldir = SPRITES / layer.name
        ldir.mkdir(parents=True, exist_ok=True)
        files: list[tuple[str, str]] = []  # (filename, description)

        if layer.sprite_pattern:  # body: variant x pose grid
            pose_layer = cfg.layer_by_name["pose"]
            for t in layer.traits:
                for p in pose_layer.traits:
                    rel = layer.sprite_pattern.format(body=_snake(t.name), pose=_snake(p.name))
                    files.append((Path(rel).name, f"{t.name} x {p.name}"))
        else:
            for t in layer.traits:
                if t.sprite_filename:
                    files.append((t.sprite_filename, t.name))

        for fname, desc in files:
            path = ldir / fname
            if path.exists() and not args.force:
                skipped += 1
                continue
            img = draw_placeholder(layer.name, f"{layer.name}/{fname}", master)
            img.save(path)
            written += 1

        lines = [
            f"# sprites/{layer.name} — {layer.display_name}",
            "",
            f"z-order: {layer.z_order} | required: {layer.required} | "
            f"dimensions: {PX}x{PX} RGBA PNG, alpha strictly 0/255, master-palette colors only",
            "",
            "> **PLACEHOLDERS**: every PNG currently in this directory is a generated",
            "> placeholder (solid fill + accent stripe + checker notch). Replace with",
            "> final art file-for-file; names and dimensions must not change.",
            "",
            "| file | trait |",
            "|---|---|",
        ]
        lines += [f"| `{f}` | {d} |" for f, d in files]
        (ldir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    log.info("placeholders: %d written, %d kept (use --force to regenerate)", written, skipped)
    return 0


def _snake(name: str) -> str:
    import re
    s = name.lower().replace("'", "").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r" +", "_", s.strip())


if __name__ == "__main__":
    sys.exit(main())
