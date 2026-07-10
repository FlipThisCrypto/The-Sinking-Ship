# SPDX-License-Identifier: MIT
"""Pixel-art compositor for THE SINKING SHIP (P4).

48x48 RGBA masters composited in traits.json z-order, with:
  - alpha binarization (a >= 128 -> 255, else 0 — no partial alpha, ever)
  - palette snapping: every layer snaps to the 32-color master palette;
    background layers (sky, sea) snap to the NFT's depth-zone sub-palette
  - nearest-neighbor upscales to 2048x2048 and 4000x4000, zero anti-aliasing

Scale-mode note (ADR-0005): 2048/48 and 4000/48 are not integers. Default
"exact" mode does a straight NEAREST resize to the exact spec sizes (pixel
columns alternate 42/43 px — imperceptible). "integer" mode uses the largest
integer factor (42x / 83x) and pads symmetrically with transparent border.

Usage:
    python engine/render_engine.py --validate-sprites
    python engine/render_engine.py --sample 25 --seed sample-run --outdir output/samples
    python engine/render_engine.py --render-manifest output/chests/<file>.json --outdir output/renders
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

from PIL import Image

from shipgen.config import GenConfig, load_json, CONFIG_DIR
from shipgen.roll import RollEngine
from shipgen.schema import validate

log = logging.getLogger("render_engine")

ROOT = Path(__file__).resolve().parent.parent
SPRITES_DIR = ROOT / "sprites"


# ------------------------------------------------------------------ palette

class Palette:
    def __init__(self, config_dir: Path = CONFIG_DIR):
        doc = load_json(config_dir / "palette.json")
        schema = load_json(config_dir / "schemas" / "palette.schema.json")
        validate(doc, schema)
        self.doc = doc
        self.master: dict[str, tuple[int, int, int]] = {
            c["name"]: _hex_rgb(c["hex"]) for c in doc["master"]
        }
        names = set(self.master)
        for zone, members in doc["zones"].items():
            unknown = set(members) - names
            if unknown:
                raise ValueError(f"palette zone {zone} references unknown colors {unknown}")
            if len(set(members)) != len(members):
                raise ValueError(f"palette zone {zone} has duplicate colors")
        self.zone_colors = {z: [self.master[n] for n in m] for z, m in doc["zones"].items()}
        self.master_colors = list(self.master.values())
        self.background_layers = set(doc["background_layers"])

    def colors_for(self, layer_name: str, zone: str | None) -> list[tuple[int, int, int]]:
        if zone and layer_name in self.background_layers:
            return self.zone_colors[zone]
        return self.master_colors


def _hex_rgb(h: str) -> tuple[int, int, int]:
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))


def _nearest(color: tuple[int, int, int], colors: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    r, g, b = color
    best, best_d = colors[0], 1 << 30
    for c in colors:
        d = (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2
        if d < best_d:
            best, best_d = c, d
    return best


# ------------------------------------------------------------------ sprites

def binarize_and_snap(img: Image.Image, colors: list[tuple[int, int, int]]) -> Image.Image:
    """Force alpha to {0,255} and snap opaque pixels to the given palette."""
    img = img.convert("RGBA")
    px = img.load()
    cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a < 128:
                px[x, y] = (0, 0, 0, 0)
            else:
                key = (r, g, b)
                snapped = cache.get(key)
                if snapped is None:
                    snapped = key if key in colors else _nearest(key, colors)
                    cache[key] = snapped
                px[x, y] = (*snapped, 255)
    return img


class SpriteStore:
    """Loads, binarizes, palette-snaps, and caches layer sprites."""

    def __init__(self, cfg: GenConfig, palette: Palette, sprites_dir: Path = SPRITES_DIR):
        self.cfg = cfg
        self.palette = palette
        self.dir = Path(sprites_dir)
        self.master_px = cfg.traits_doc["grid"]["master_px"]
        self._cache: dict[tuple, Image.Image] = {}

    def sprite_path(self, layer_name: str, traits: dict[str, str]) -> Path | None:
        layer = self.cfg.layer_by_name[layer_name]
        if layer.rendered_via:
            return None
        trait_name = traits.get(layer_name)
        if trait_name is None:
            return None
        if layer.sprite_pattern:
            parts = {ln: _snake(traits[ln]) for ln in (layer_name, *_pattern_deps(layer))}
            rel = layer.sprite_pattern.format(**parts)
            return self.dir / rel
        trait = layer.traits[layer.trait_index[trait_name]]
        if trait.sprite_filename is None:
            return None  # e.g. "None" traits
        return self.dir / layer_name / trait.sprite_filename

    def get(self, layer_name: str, traits: dict[str, str], zone: str | None) -> Image.Image | None:
        path = self.sprite_path(layer_name, traits)
        if path is None:
            return None
        zone_key = zone if layer_name in self.palette.background_layers else None
        key = (str(path), zone_key)
        img = self._cache.get(key)
        if img is None:
            if not path.exists():
                raise FileNotFoundError(f"missing sprite: {path}")
            img = Image.open(path)
            if img.size != (self.master_px, self.master_px):
                raise ValueError(f"{path}: expected {self.master_px}x{self.master_px}, "
                                 f"got {img.size[0]}x{img.size[1]}")
            img = binarize_and_snap(img, self.palette.colors_for(layer_name, zone_key))
            self._cache[key] = img
        return img


def _pattern_deps(layer) -> list[str]:
    """Other layer names referenced by a sprite_pattern (e.g. body needs pose)."""
    import string
    fields = [f for _, f, _, _ in string.Formatter().parse(layer.sprite_pattern) if f]
    return [f for f in fields if f != layer.name]


def _snake(name: str) -> str:
    import re
    s = name.lower().replace("'", "").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r" +", "_", s.strip())


# ---------------------------------------------------------------- composite

def compose(store: SpriteStore, traits: dict[str, str], zone: str | None) -> Image.Image:
    cfg = store.cfg
    size = store.master_px
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layers = sorted((l for l in cfg.layers if l.z_order is not None),
                    key=lambda l: l.z_order)
    for layer in layers:
        sprite = store.get(layer.name, traits, zone)
        if sprite is not None:
            canvas.alpha_composite(sprite)
    return canvas


def upscale(img: Image.Image, target: int, mode: str) -> Image.Image:
    if mode == "exact":
        return img.resize((target, target), Image.NEAREST)
    factor = target // img.width
    core = img.resize((img.width * factor, img.height * factor), Image.NEAREST)
    pad = target - core.width
    if pad == 0:
        return core
    out = Image.new("RGBA", (target, target), (0, 0, 0, 0))
    out.paste(core, (pad // 2, pad // 2))
    return out


# --------------------------------------------------------------- validation

def validate_sprites(cfg: GenConfig, palette: Palette, sprites_dir: Path) -> int:
    """Scan the sprite tree against traits.json. Returns error count."""
    master_px = cfg.traits_doc["grid"]["master_px"]
    errors = warnings = checked = 0

    def check(path: Path, layer_name: str):
        nonlocal errors, warnings, checked
        checked += 1
        if not path.exists():
            log.error("MISSING  %s", path.relative_to(sprites_dir))
            errors += 1
            return
        img = Image.open(path).convert("RGBA")
        if img.size != (master_px, master_px):
            log.error("BAD SIZE %s: %dx%d (want %dx%d)",
                      path.relative_to(sprites_dir), *img.size, master_px, master_px)
            errors += 1
            return
        colors = set(palette.master_colors)
        semi = off = 0
        for _, (r, g, b, a) in img.getcolors(maxcolors=master_px * master_px) or []:
            if a not in (0, 255):
                semi += 1
            elif a == 255 and (r, g, b) not in colors:
                off += 1
        if semi:
            log.warning("SEMI-ALPHA %s: %d semi-transparent color(s) "
                        "(binarized at render time)", path.relative_to(sprites_dir), semi)
            warnings += 1
        if off:
            log.warning("OFF-PALETTE %s: %d color(s) not in master palette "
                        "(snapped at render time)", path.relative_to(sprites_dir), off)
            warnings += 1

    for layer in cfg.layers:
        if layer.rendered_via:
            continue
        if layer.sprite_pattern:
            deps = _pattern_deps(layer)
            dep_layer = cfg.layer_by_name[deps[0]]
            for t in layer.traits:
                for d in dep_layer.traits:
                    rel = layer.sprite_pattern.format(**{layer.name: _snake(t.name),
                                                         deps[0]: _snake(d.name)})
                    check(sprites_dir / rel, layer.name)
        else:
            for t in layer.traits:
                if t.sprite_filename:
                    check(sprites_dir / layer.name / t.sprite_filename, layer.name)

    log.info("checked %d sprites: %d error(s), %d warning(s)", checked, errors, warnings)
    return errors


# --------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate-sprites", action="store_true")
    ap.add_argument("--sample", type=int, metavar="N", help="roll and render N sample NFTs")
    ap.add_argument("--seed", default="sample", help="sample mode: deterministic seed")
    ap.add_argument("--zone", default=None,
                    help="zone sub-palette for backgrounds in sample mode (default: cycle)")
    ap.add_argument("--render-manifest", metavar="FILE", help="render a chest manifest")
    ap.add_argument("--outdir", default="output/renders")
    ap.add_argument("--sizes", default="48,2048,4000",
                    help="comma list of output sizes (default 48,2048,4000)")
    ap.add_argument("--scale-mode", choices=["exact", "integer"], default="exact")
    ap.add_argument("--sprites-dir", default=str(SPRITES_DIR))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = GenConfig()
    palette = Palette()
    sprites_dir = Path(args.sprites_dir)

    if args.validate_sprites:
        errors = validate_sprites(cfg, palette, sprites_dir)
        return 1 if errors else 0

    store = SpriteStore(cfg, palette, sprites_dir)
    sizes = [int(s) for s in args.sizes.split(",")]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    zones = cfg.tiers_doc["depth_zones"]

    jobs: list[tuple[str, dict, str]] = []  # (name, traits, zone)
    if args.sample:
        engine = RollEngine(cfg)
        salt = hashlib.sha256(f"render-sample:{args.seed}".encode()).digest()
        for i in range(args.sample):
            nft = engine.roll_nft(salt, f"sample/{i}")
            zone = args.zone or zones[i % len(zones)]
            jobs.append((f"sample_{i:03d}_{nft.rarity_tier}", nft.traits, zone))
    elif args.render_manifest:
        manifest = load_json(Path(args.render_manifest))
        zone = manifest["zone"]
        for e in manifest["nfts"]:
            if e["type"] != "generated":
                continue  # grails are hand-made 1/1s, not composited
            jobs.append((f"nft_{e['global_index']:05d}", e["traits"], zone))
    else:
        ap.error("choose one of --validate-sprites / --sample / --render-manifest")

    for name, traits, zone in jobs:
        img = compose(store, traits, zone)
        for size in sizes:
            out = img if size == store.master_px else upscale(img, size, args.scale_mode)
            path = outdir / f"{name}_{size}.png"
            out.save(path)
        log.info("rendered %s (%s) at %s", name, zone, ",".join(map(str, sizes)))
    log.info("done: %d NFT(s) -> %s", len(jobs), outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
