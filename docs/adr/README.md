# Architecture Decision Records

| # | Title | Core decision |
|---|---|---|
| [0001](ADR-0001-patterns-adopted-from-reference-implementation.md) | Patterns adopted from reference implementation | What we adopt / adapt / deliberately do differently vs the BEPE LOVE production repo |
| [0002](ADR-0002-deterministic-rng-and-commit-reveal.md) | Deterministic RNG & commit–reveal | HMAC-SHA256 DRBG, named substreams, integer-only draws, canonical-JSON hashing |
| [0003](ADR-0003-constraint-engine-design.md) | Constraint engine | Forward-biased sequential rolls + deterministic rejection + pre-committed quota slots |
| [0004](ADR-0004-tier-math-and-supply-model.md) | Tier math & supply model | Uniform chest quantities, luck on Epic+, pity mechanics, the OQ-1 supply overflow |
| [0005](ADR-0005-palette-and-upscale-strategy.md) | Palette & upscale strategy | Sub-palettes as master subsets; exact-size NN upscale despite non-integer factors |
| [0006](ADR-0006-weight-tuning-methodology.md) | Weight tuning methodology | Generated weights.json, sellout-mixture objective, replicated acceptance protocol |
| [0007](ADR-0007-config-schema-validation.md) | Config schema validation | Real JSON Schemas + minimal stdlib validator + cross-file consistency checks |

Open questions for the project owner are tagged **OQ-1 … OQ-9** across these
ADRs and the config `notes` fields; `git grep "OQ-"` lists every site.
