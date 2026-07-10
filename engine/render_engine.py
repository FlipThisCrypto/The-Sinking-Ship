# SPDX-License-Identifier: MIT
"""Layer compositor for THE SINKING SHIP (P4), profile-driven (ADR-0008).

Two render profiles, selected by config/render.json `active_profile` (or the
`--profile` flag):

  pixel        — the original spec behaviour: 48x48 masters, alpha binarization
                 (no partial alpha), palette snapping, nearest-neighbour upscale
                 to 2048/4000 with zero anti-aliasing.
  illustration — the owner-chosen Amano medium: native high-res layer art
                 composited with FULL alpha (no binarization), NO palette snap
                 (palette is a soft guide), LANCZOS resample to the output
                 sizes. This is the active profile.

Both share one code path; the profile flags toggle the pixel-specific cleanup.
Trait selection, rarity, fairness, and metadata are medium-independent and
untouched — this file only renders a chosen trait manifest.

Usage:
    python engine/render_engine.py --validate-sprites
    python engine/render_engine.py --sample 25 --seed s --outdir output/samples
    python engine/render_engine.py --render-manifest output/chests/<f>.json --outdir out
    python engine/render_engine.py --profile pixel --validate-sprites
"""
from __future__ import annotations

import argparse
import hashlib
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

_RESAMPLE = {"nearest": Image.NEAREST, "lanczos": Image.LANCZOS}


# ------------------------------------------------------------------ profile

class RenderProfile:
    def __init__(self, name: str, spec: dict):
        self.name = name
        self.master_px = int(spec["master_px"])
        self.binarize_alpha = bool(spec["binarize_alpha"])
        self.palette_snap = bool(spec["palette_snap"])
        self.resample = spec["resample"]
        self.outputs = list(spec["outputs"])
        self.layer_transforms = dict(spec.get("layer_transforms", {}))

    @property
    def resample_filter(self):
        return _RESAMPLE[self.resample]


def load_profile(name: str | None, config_dir: Path = CONFIG_DIR) -> RenderProfile:
    doc = load_json(config_dir / "render.json")
    validate(doc, load_json(config_dir / "schemas" / "render.schema.json"))
    chosen = name or doc["active_profile"]
    if chosen not in doc["profiles"]:
        raise ValueError(f"unknown render profile {chosen!r}")
    return RenderProfile(chosen, doc["profiles"][chosen])


# ------------------------------------------------------------------ palette

class Palette:
    def __init__(self, config_dir: Path = CONFIG_DIR):
        doc = load_json(config_dir / "palette.json")
        validate(doc, load_json(config_dir / "schemas" / "palette.schema.json"))
        self.doc = doc
        self.master = {c["name"]: _hex_rgb(c["hex"]) for c in doc["master"]}
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


def _nearest(color, colors):
    r, g, b = color
    best, best_d = colors[0], 1 << 30
    for c in colors:
        d = (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2
        if d < best_d:
            best, best_d = c, d
    return best


# ------------------------------------------------------------------ sprites

def prepare_sprite(img: Image.Image, colors, binarize: bool, snap: bool) -> Image.Image:
    """Apply the profile's cleanup. In illustration mode both flags are off and
    the sprite passes through as authored (full alpha, any colours)."""
    img = img.convert("RGBA")
    if not binarize and not snap:
        return img
    px = img.load()
    cache: dict = {}
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if binarize and a < 128:
                px[x, y] = (0, 0, 0, 0)
                continue
            out_a = 255 if binarize else a
            if snap and out_a > 0:
                key = (r, g, b)
                sc = cache.get(key)
                if sc is None:
                    sc = key if key in colors else _nearest(key, colors)
                    cache[key] = sc
                px[x, y] = (*sc, out_a)
            else:
                px[x, y] = (r, g, b, out_a)
    return img


class SpriteStore:
    def __init__(self, cfg: GenConfig, palette: Palette, profile: RenderProfile,
                 sprites_dir: Path = SPRITES_DIR):
        self.cfg = cfg
        self.palette = palette
        self.profile = profile
        self.dir = Path(sprites_dir)
        self.master_px = profile.master_px
        self._cache: dict = {}

    def sprite_path(self, layer_name: str, traits: dict) -> Path | None:
        layer = self.cfg.layer_by_name[layer_name]
        if layer.rendered_via:
            return None
        trait_name = traits.get(layer_name)
        if trait_name is None:
            return None
        if layer.sprite_pattern:
            parts = {ln: _snake(traits[ln]) for ln in (layer_name, *_pattern_deps(layer))}
            return self.dir / layer.sprite_pattern.format(**parts)
        trait = layer.traits[layer.trait_index[trait_name]]
        if trait.sprite_filename is None:
            return None
        return self.dir / layer_name / trait.sprite_filename

    def get(self, layer_name: str, traits: dict, zone: str | None) -> Image.Image | None:
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
                raise ValueError(f"{path}: expected {self.master_px}x{self.master_px} "
                                 f"for the {self.profile.name} profile, got "
                                 f"{img.size[0]}x{img.size[1]}")
            colors = self.palette.colors_for(layer_name, zone_key)
            img = prepare_sprite(img, colors, self.profile.binarize_alpha,
                                 self.profile.palette_snap)
            self._cache[key] = img
        return img


def _pattern_deps(layer) -> list[str]:
    import string
    fields = [f for _, f, _, _ in string.Formatter().parse(layer.sprite_pattern) if f]
    return [f for f in fields if f != layer.name]


def _snake(name: str) -> str:
    import re
    s = name.lower().replace("'", "").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r" +", "_", s.strip())


# ---------------------------------------------------------------- composite

def _zone_ramp_name(zone: str | None) -> str:
    """Map depth zone → ships_amano vertical ink ramp (always warm→cool)."""
    return {
        "surface": "crimson_navy",
        "sunlight": "gold_navy",
        "twilight": "violet_navy",
        "midnight": "green_navy",
        "abyssal": "ember_ink",
        "hadal": "green_navy",
    }.get(zone or "", "crimson_navy")


def compose(store: SpriteStore, traits: dict, zone: str | None) -> Image.Image:
    size = store.master_px
    # Illustration: bone-white ground (ships_amano / ART-DIRECTION). Pixel: clear.
    if store.profile.name == "illustration":
        bone = store.palette.master.get("bone_white", (244, 244, 240))
        canvas = Image.new("RGBA", (size, size), (*bone, 255))
    else:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layers = sorted((l for l in store.cfg.layers if l.z_order is not None),
                    key=lambda l: l.z_order)
    for layer in layers:
        sprite = store.get(layer.name, traits, zone)
        if sprite is None:
            continue
        tf = store.profile.layer_transforms.get(layer.name)
        if tf and float(tf.get("scale", 1.0)) != 1.0:
            # margin discipline: scale about horizontal center, anchored
            # vertically (1.0 = bottom stays put) so grounding is preserved
            sc = float(tf["scale"])
            new = sprite.resize((max(1, round(size * sc)),) * 2, Image.LANCZOS)
            ax = (size - new.width) // 2
            ay = round(float(tf.get("anchor_y", 1.0)) * (size - new.height))
            layer_canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            layer_canvas.paste(new, (ax, ay))
            sprite = layer_canvas
        canvas.alpha_composite(sprite)
    if store.profile.name == "illustration":
        # Global vertical ink grade — the ships_amano signature on every mint.
        from shipgen.amano_ink import RAMPS, grade_vertical_ink
        canvas = grade_vertical_ink(
            canvas, stops=RAMPS[_zone_ramp_name(zone)], strength=0.84,
        )
    return canvas


def resize_to(img: Image.Image, target: int, profile: RenderProfile,
              scale_mode: str) -> Image.Image:
    if target == img.width:
        return img
    if profile.resample == "nearest" and scale_mode == "integer" and target > img.width:
        factor = target // img.width
        core = img.resize((img.width * factor, img.height * factor), Image.NEAREST)
        pad = target - core.width
        if pad == 0:
            return core
        out = Image.new("RGBA", (target, target), (0, 0, 0, 0))
        out.paste(core, (pad // 2, pad // 2))
        return out
    return img.resize((target, target), profile.resample_filter)


# --------------------------------------------------------------- validation

def validate_sprites(cfg: GenConfig, palette: Palette, profile: RenderProfile,
                     sprites_dir: Path) -> int:
    master_px = profile.master_px
    errors = warnings = checked = 0
    strict_pixels = profile.binarize_alpha or profile.palette_snap

    def check(path: Path):
        nonlocal errors, warnings, checked
        checked += 1
        if not path.exists():
            log.error("MISSING  %s", path.relative_to(sprites_dir))
            errors += 1
            return
        img = Image.open(path).convert("RGBA")
        if img.size != (master_px, master_px):
            log.error("BAD SIZE %s: %dx%d (want %dx%d for %s profile)",
                      path.relative_to(sprites_dir), *img.size, master_px, master_px,
                      profile.name)
            errors += 1
            return
        if not strict_pixels:
            return  # illustration: AA + off-palette are expected, nothing to flag
        colors = set(palette.master_colors)
        semi = off = 0
        for _, (r, g, b, a) in img.getcolors(maxcolors=master_px * master_px) or []:
            if a not in (0, 255):
                semi += 1
            elif a == 255 and (r, g, b) not in colors:
                off += 1
        if semi:
            log.warning("SEMI-ALPHA %s: %d colour(s) (binarized at render time)",
                        path.relative_to(sprites_dir), semi)
            warnings += 1
        if off:
            log.warning("OFF-PALETTE %s: %d colour(s) (snapped at render time)",
                        path.relative_to(sprites_dir), off)
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
                    check(sprites_dir / rel)
        else:
            for t in layer.traits:
                if t.sprite_filename:
                    check(sprites_dir / layer.name / t.sprite_filename)

    log.info("[%s profile] checked %d sprites: %d error(s), %d warning(s)",
             profile.name, checked, errors, warnings)
    return errors


# --------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate-sprites", action="store_true")
    ap.add_argument("--sample", type=int, metavar="N")
    ap.add_argument("--seed", default="sample")
    ap.add_argument("--zone", default=None)
    ap.add_argument("--render-manifest", metavar="FILE")
    ap.add_argument("--outdir", default="output/renders")
    ap.add_argument("--profile", choices=["pixel", "illustration"], default=None,
                    help="override config/render.json active_profile")
    ap.add_argument("--sizes", default=None, help="comma list; default = profile outputs")
    ap.add_argument("--scale-mode", choices=["exact", "integer"], default="exact",
                    help="pixel profile only: integer adds symmetric padding")
    ap.add_argument("--sprites-dir", default=str(SPRITES_DIR))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = GenConfig()
    palette = Palette()
    profile = load_profile(args.profile)
    sprites_dir = Path(args.sprites_dir)
    log.info("render profile: %s (master %dpx, binarize=%s, snap=%s, resample=%s)",
             profile.name, profile.master_px, profile.binarize_alpha,
             profile.palette_snap, profile.resample)

    if args.validate_sprites:
        return 1 if validate_sprites(cfg, palette, profile, sprites_dir) else 0

    store = SpriteStore(cfg, palette, profile, sprites_dir)
    sizes = ([int(s) for s in args.sizes.split(",")] if args.sizes else profile.outputs)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    zones = cfg.tiers_doc["depth_zones"]

    jobs = []
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
            if e["type"] == "generated":
                jobs.append((f"nft_{e['global_index']:05d}", e["traits"], zone))
    else:
        ap.error("choose one of --validate-sprites / --sample / --render-manifest")

    for name, traits, zone in jobs:
        img = compose(store, traits, zone)
        for size in sizes:
            out = resize_to(img, size, profile, args.scale_mode)
            out.save(outdir / f"{name}_{size}.png")
        log.info("rendered %s (%s) at %s", name, zone, ",".join(map(str, sizes)))
    log.info("done: %d NFT(s) -> %s", len(jobs), outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
