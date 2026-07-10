# SPDX-License-Identifier: MIT
"""Minimal JSON Schema validator (stdlib only).

The engineering conventions forbid third-party deps beyond Pillow/numpy in
the core engine, so we validate configs with a deliberately small subset of
JSON Schema draft 2020-12 — exactly the keywords our schemas use:

    type, const, enum, required, properties, items, minItems, maxItems,
    minimum, maximum, pattern, $ref (into local $defs only)

Unknown keywords are ignored (matching JSON Schema semantics). This is not a
general-purpose validator; it is a guardrail that fails loudly when a config
drifts from its schema. See ADR-0007.
"""
from __future__ import annotations

import re
from typing import Any

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


class SchemaError(ValueError):
    pass


def validate(instance: Any, schema: dict, root: dict | None = None, path: str = "$") -> None:
    """Raise SchemaError with a JSONPath-ish location on first violation."""
    if root is None:
        root = schema

    ref = schema.get("$ref")
    if ref is not None:
        if not ref.startswith("#/$defs/"):
            raise SchemaError(f"{path}: unsupported $ref {ref!r}")
        name = ref[len("#/$defs/"):]
        target = root.get("$defs", {}).get(name)
        if target is None:
            raise SchemaError(f"{path}: unresolved $ref {ref!r}")
        validate(instance, target, root, path)
        return

    if "const" in schema and instance != schema["const"]:
        raise SchemaError(f"{path}: expected const {schema['const']!r}, got {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaError(f"{path}: {instance!r} not in enum {schema['enum']!r}")

    stype = schema.get("type")
    if stype is not None:
        types = stype if isinstance(stype, list) else [stype]
        if not any(_TYPE_CHECKS[t](instance) for t in types):
            raise SchemaError(f"{path}: expected type {types}, got {type(instance).__name__}")

    if isinstance(instance, str) and "pattern" in schema:
        if re.search(schema["pattern"], instance) is None:
            raise SchemaError(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaError(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaError(f"{path}: {instance} > maximum {schema['maximum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                raise SchemaError(f"{path}: missing required key {key!r}")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in instance:
                validate(instance[key], sub, root, f"{path}.{key}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise SchemaError(f"{path}: {len(instance)} items < minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise SchemaError(f"{path}: {len(instance)} items > maxItems {schema['maxItems']}")
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(instance):
                validate(item, items, root, f"{path}[{i}]")
