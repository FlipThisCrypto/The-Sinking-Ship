# vault/ — frozen sprite originals

Immutable, byte-exact snapshots of `sprites/` taken **before** an art revision
round. Read-only by convention: nothing in this tree is ever edited in place.

| vault | frozen from | files | contents |
|---|---|---|---|
| `sprites-v1/` | `sprites/` @ commit `1efd7d9` (2026-08-04) | 216 | the pre-round-3 art: real illustration in `body/` + `ship_class/`, procedural stand-ins elsewhere |
| `sprites-v2/` | `sprites/` @ commit `387cd4f` (2026-08-05) | 216 | the whole layer set as shipped through iteration 14, frozen before the face-blanking work begins. This is the revert point for the current look. |

## Why this exists

`body/` and `ship_class/` were authored **outside this repository** and have no
reproducible generator here — `scripts/gen_placeholder_sprites.py` would
overwrite them with procedural stand-ins if run with `--force`. Once
overwritten they cannot be recovered from code. `vault/sprites-v1/` is the
reference copy.

The other nine layers were procedural stand-ins; `sprites-v1` records exactly
what they were so any regression is provable rather than remembered.

## Tooling

```bash
python scripts/vault_tool.py verify          # re-hash the vault against its manifest
python scripts/vault_tool.py diff            # what has changed in sprites/ since the freeze
python scripts/vault_tool.py freeze v2       # snapshot the current sprites/ as a new vault
```

`MANIFEST.sha256` in each vault is a standard `sha256sum` file (LF endings,
sorted by path), so `sha256sum -c MANIFEST.sha256` works too.

`freeze` refuses to write into an existing vault directory — vaults are
append-only, never amended.

## Known facts about `sprites-v1` (measured at freeze time)

- Master size is **2048×2048 RGBA** for every PNG.
- All 15 `sky/`, 11 `sea/`, 9 `aura/`, 11 `ship_condition/`, 14 `clothing/`,
  16 `eyes/`, 10 `mouth/`, 14 `hat/` and 40 `scene_element/` files are
  **fully transparent** — the stand-in generator emitted empty canvases, which
  is why they read as black in a viewer.
- `body/` holds 48 filenames but only **12 unique images**: `blue`, `emerald`,
  `green` and `zombie` are byte-identical to one another, and `chrome`,
  `corrupted`, `ghost` and `gold` repeat one image across all six poses.
- `ship_class/` holds 16 genuinely distinct illustrations — the strongest
  material in the vault.
