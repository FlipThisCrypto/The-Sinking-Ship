# ADR-0007 — Config validation: JSON Schema files + a minimal stdlib validator

**Status:** Accepted
**Date:** 2026-07-10

## Context

Everything is config-driven (traits, weights, tiers, palette), and the
engineering conventions require JSON Schema validation — but also restrict
the core engine to stdlib + Pillow + numpy, which excludes the `jsonschema`
package.

## Decision

- Every config ships a real JSON Schema (draft 2020-12) in
  `config/schemas/`, usable by any external tool or IDE as-is.
- The engine validates with `shipgen/schema.py`, a ~100-line validator for
  exactly the keyword subset our schemas use (`type, const, enum, required,
  properties, items, minItems, maxItems, minimum, maximum, pattern, $ref`
  into local `$defs`). Unknown keywords are ignored, matching JSON Schema
  semantics.
- Structural facts a schema can't express are enforced by cross-checks in
  `shipgen/config.py`: every trait weighted exactly once, no unknown
  traits, constraint references resolve, roll_order covers all layers, and
  weights.json's depth_luck/guarantees copies must equal tiers.json
  (single source of truth).

## Consequences

- Configs are validated on every load — the CLI `engine/validate_configs.py`
  is just a thin wrapper — so a drifted config fails at startup, not
  mid-mint.
- The validator is deliberately not general-purpose; if a schema starts
  using an unsupported keyword, the schema tests must grow with it. That
  trade is accepted to keep the fairness path dependency-free.
