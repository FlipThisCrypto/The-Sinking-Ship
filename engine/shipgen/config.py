# SPDX-License-Identifier: MIT
"""Config loading, schema validation, and cross-file consistency checks.

All generation behavior is config-driven: trait names, weights, tier prices,
odds, and constraint multipliers live in config/*.json — never in Python.
Every loader validates against the JSON Schema in config/schemas/ and the
bundle hash of all loaded configs is embedded in every manifest.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .canon import config_bundle_hash
from .schema import validate
from . import RARITY_RANK

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_validated(name: str, config_dir: Path) -> dict:
    doc = load_json(config_dir / f"{name}.json")
    schema = load_json(config_dir / "schemas" / f"{name}.schema.json")
    validate(doc, schema)
    return doc


@dataclass
class Trait:
    name: str
    sprite_filename: str | None
    rarity_bucket: str
    series: str | None = None

    @property
    def rarity_rank(self) -> int:
        # 'none' and 'quota' traits never drive the rarity tier
        return RARITY_RANK.get(self.rarity_bucket, -1)


@dataclass
class Layer:
    name: str
    display_name: str
    z_order: int | None
    required: bool
    traits: list[Trait]
    sprite_pattern: str | None = None
    rendered_via: str | None = None
    trait_index: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.trait_index = {t.name: i for i, t in enumerate(self.traits)}


class GenConfig:
    """The full, validated, cross-checked configuration bundle."""

    def __init__(self, config_dir: Path | None = None, require_weights: bool = True):
        config_dir = Path(config_dir) if config_dir else CONFIG_DIR
        self.traits_doc = _load_validated("traits", config_dir)
        self.tiers_doc = _load_validated("tiers", config_dir)
        self.weights_doc = _load_validated("weights", config_dir) if require_weights else None

        self.layers: list[Layer] = []
        for ld in self.traits_doc["layers"]:
            self.layers.append(Layer(
                name=ld["name"],
                display_name=ld["display_name"],
                z_order=ld["z_order"],
                required=ld["required"],
                sprite_pattern=ld.get("sprite_pattern"),
                rendered_via=ld.get("rendered_via"),
                traits=[Trait(t["name"], t["sprite_filename"], t["rarity_bucket"],
                              t.get("series")) for t in ld["traits"]],
            ))
        self.layer_by_name = {ly.name: ly for ly in self.layers}
        self.roll_order: list[str] = list(self.traits_doc["roll_order"])
        self.exclusions = self.traits_doc["exclusions"]
        self.pairings = self.traits_doc["pairings"]
        self.quotas = self.traits_doc["quotas"]
        self.rules = self.traits_doc["rules"]

        self.tiers = {t["name"]: t for t in self.tiers_doc["tiers"]}
        self.supply = self.tiers_doc["supply"]
        self.grail_seeding = self.tiers_doc["grail_seeding"]

        self._check_traits()
        if self.weights_doc is not None:
            self.weights = self.weights_doc["weights"]
            self._check_weights()
            self.config_hash = config_bundle_hash(
                ("traits", self.traits_doc),
                ("weights", self.weights_doc),
                ("tiers", self.tiers_doc),
            )
        else:
            self.weights = None
            self.config_hash = None

    # ---- cross-file consistency ----

    def _check_traits(self) -> None:
        errs: list[str] = []
        if sorted(self.roll_order) != sorted(self.layer_by_name):
            errs.append("roll_order must list every layer exactly once")
        for layer in self.layers:
            names = [t.name for t in layer.traits]
            if len(names) != len(set(names)):
                errs.append(f"duplicate trait names in layer {layer.name}")
        for rule in self.exclusions + self.pairings:
            for layer, trait in _constraint_refs(rule):
                lay = self.layer_by_name.get(layer)
                if lay is None:
                    errs.append(f"{rule['id']}: unknown layer {layer}")
                elif trait is not None and trait not in lay.trait_index:
                    errs.append(f"{rule['id']}: unknown trait {trait!r} in {layer}")
        if errs:
            raise ValueError("traits.json consistency errors:\n" + "\n".join(errs))

    def _check_weights(self) -> None:
        errs: list[str] = []
        for layer in self.layers:
            wl = self.weights.get(layer.name)
            if wl is None:
                errs.append(f"weights.json missing layer {layer.name}")
                continue
            for t in layer.traits:
                if t.name not in wl:
                    errs.append(f"weights.json missing {layer.name}/{t.name}")
            for name in wl:
                if name not in layer.trait_index:
                    errs.append(f"weights.json has unknown trait {layer.name}/{name}")
        # depth_luck / guarantees copies must match tiers.json (single source of truth)
        wd = self.weights_doc
        for tier in self.tiers_doc["tiers"]:
            name = tier["name"]
            if wd["depth_luck"].get(name) != tier["depth_luck_permille"]:
                errs.append(f"weights.json depth_luck[{name}] != tiers.json depth_luck_permille")
            if wd["guarantees"].get(name) != tier["guarantee"]:
                errs.append(f"weights.json guarantees[{name}] != tiers.json guarantee")
        if errs:
            raise ValueError("weights/tiers consistency errors:\n" + "\n".join(errs))

    # ---- convenience ----

    def weight_of(self, layer: str, trait: str) -> int:
        return int(self.weights[layer][trait])


def _constraint_refs(rule: dict):
    if "if" in rule:
        yield rule["if"]["layer"], rule["if"]["trait"]
    then = rule.get("then")
    if isinstance(then, dict):
        for t in then.get("traits", []):
            yield then["layer"], t
        for alt in then.get("any_of", []):
            for t in alt["traits"]:
                yield alt["layer"], t
    elif isinstance(then, list):
        for part in then:
            for t in part["traits"]:
                yield part["layer"], t
    for member in rule.get("cluster_traits", []) + rule.get("combo", []):
        yield member["layer"], member["trait"]
