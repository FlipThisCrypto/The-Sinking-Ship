# SPDX-License-Identifier: MIT
"""Tests for shipgen/schema.py $ref resolution and keyword validation."""
from __future__ import annotations

import pytest

from shipgen.schema import SchemaError, validate


def test_schema_ref_defs_resolution():
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["item"],
        "properties": {
            "item": {"$ref": "#/$defs/custom_type"},
        },
        "$defs": {
            "custom_type": {
                "type": "string",
                "pattern": "^[A-Z]{3}$",
            },
        },
    }

    # Valid instance
    validate({"item": "ABC"}, schema)

    # Invalid pattern
    with pytest.raises(SchemaError, match="pattern"):
        validate({"item": "abc"}, schema)


def test_unsupported_or_unresolved_ref():
    # Unsupported external $ref
    schema_ext = {"$ref": "https://example.com/schema.json"}
    with pytest.raises(SchemaError, match="unsupported \\$ref"):
        validate({"a": 1}, schema_ext)

    # Unresolved internal $ref
    schema_missing = {"$ref": "#/$defs/missing"}
    with pytest.raises(SchemaError, match="unresolved \\$ref"):
        validate({"a": 1}, schema_missing)


def test_schema_number_and_array_boundaries():
    schema = {
        "type": "object",
        "properties": {
            "val": {"type": "number", "minimum": 0.0, "maximum": 100.0},
            "tags": {"type": "array", "minItems": 1, "maxItems": 3},
        },
    }

    validate({"val": 50.5, "tags": ["a", "b"]}, schema)

    with pytest.raises(SchemaError, match="minimum"):
        validate({"val": -1.0}, schema)

    with pytest.raises(SchemaError, match="maximum"):
        validate({"val": 150.0}, schema)

    with pytest.raises(SchemaError, match="maxItems"):
        validate({"tags": ["1", "2", "3", "4"]}, schema)
