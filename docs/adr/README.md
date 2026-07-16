# Architecture Decision Records

| # | Title | Core decision |
|---|---|---|
| [0001](ADR-0001-patterns-adopted-from-reference-implementation.md) | Patterns from reference | Adopt / adapt / refuse vs BEPE LOVE |
| [0002](ADR-0002-deterministic-rng-and-commit-reveal.md) | Deterministic RNG & commit–reveal | HMAC-SHA256 DRBG, integer draws |
| [0003](ADR-0003-constraint-engine-design.md) | Constraint engine | Forward rolls + rejection + quotas; OQ-3/10 resolved |
| [0004](ADR-0004-tier-math-and-supply-model.md) | Tier math & supply | OQ-1/2/4 resolved (trim passes, 10× luck, auction 11) |
| [0005](ADR-0005-palette-and-upscale-strategy.md) | Palette & upscale | Zone subsets; NN / Lanczos by profile |
| [0006](ADR-0006-weight-tuning-methodology.md) | Weight tuning | Sellout-mixture objective (OQ-5) |
| [0007](ADR-0007-config-schema-validation.md) | Config schemas | Stdlib validator + cross-file checks |
| [0008](ADR-0008-art-medium-full-amano-illustration.md) | Art medium | Full Amano illustration (OQ-11) |

## Open questions status

| ID | Topic | Status |
|---|---|---|
| OQ-1 | Supply overflow | **Resolved** — Snorkeler pass trim |
| OQ-2 | Wizard Depth Luck ∞ | **Resolved** — finite 10.0× |
| OQ-3 | Torn under Scuttling | **Resolved** — “up to 44” |
| OQ-4 | Auction 11 vs 12 | **Resolved** — auction 11 |
| OQ-5 | Rarity targets mixture | **Resolved** — full-sellout mixture |
| OQ-7 | Print upscale mode | Open (owner, non-blocking) |
| OQ-10 | Ghost Fade exclusivity | **Resolved** — keep 8× bias |
| OQ-11 | Pixel vs illustration | **Resolved** — Amano illustration |

`git grep "OQ-"` lists every remaining mention in the tree.
