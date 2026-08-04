# SPDX-License-Identifier: MIT
"""Art vault: freeze, verify, and diff the sprite tree against an immutable copy.

The vault under ``vault/sprites-vN/`` is a byte-exact snapshot of ``sprites/``
taken before an art revision round. It exists because several sprite layers
(``body/``, ``ship_class/``) were authored externally and have **no
reproducible generator in this repository** — once overwritten they are gone.

Subcommands
-----------
freeze  <version>   Copy sprites/ -> vault/sprites-<version>/ and write MANIFEST.sha256.
verify  [version]   Re-hash the vault and compare against its manifest (integrity).
diff    [version]   Compare the live sprites/ tree against the vault (drift report).

Exit codes: 0 clean, 1 mismatch/corruption, 2 usage or missing vault.

Usage:
    python scripts/vault_tool.py verify
    python scripts/vault_tool.py diff --version v1
    python scripts/vault_tool.py freeze v2
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "sprites"
VAULT = ROOT / "vault"
MANIFEST_NAME = "MANIFEST.sha256"
_CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def walk_tree(root: Path) -> list[Path]:
    """Every regular file under *root*, sorted by POSIX-relative path.

    The manifest excludes itself so ``freeze`` is idempotent.
    """
    out = [
        p
        for p in root.rglob("*")
        if p.is_file() and p.name != MANIFEST_NAME
    ]
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def hash_tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): sha256_file(p) for p in walk_tree(root)
    }


def write_manifest(root: Path, entries: dict[str, str]) -> Path:
    """Write a ``sha256sum``-compatible manifest (LF endings, sorted)."""
    path = root / MANIFEST_NAME
    lines = [f"{digest}  {rel}\n" for rel, digest in sorted(entries.items())]
    path.write_text("".join(lines), encoding="utf-8", newline="\n")
    return path


def read_manifest(root: Path) -> dict[str, str]:
    path = root / MANIFEST_NAME
    if not path.exists():
        raise FileNotFoundError(path)
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, rel = line.partition("  ")
        if not rel:
            raise ValueError(f"malformed manifest line: {line!r}")
        entries[rel] = digest
    return entries


def vault_dir(version: str) -> Path:
    return VAULT / f"sprites-{version}"


def latest_version() -> str:
    """Highest ``sprites-vN`` present, e.g. ``v2``. Raises if the vault is empty."""
    versions = sorted(
        (p.name.removeprefix("sprites-") for p in VAULT.glob("sprites-v*") if p.is_dir()),
        key=lambda v: int(v.lstrip("v") or 0),
    )
    if not versions:
        raise FileNotFoundError(f"no sprites-v* directory under {VAULT}")
    return versions[-1]


# ------------------------------------------------------------------ commands


def cmd_freeze(version: str) -> int:
    dest = vault_dir(version)
    if dest.exists():
        print(f"REFUSED: {dest} already exists — vaults are immutable.", file=sys.stderr)
        return 2
    dest.mkdir(parents=True)
    for src in walk_tree(SPRITES):
        rel = src.relative_to(SPRITES)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
    entries = hash_tree(dest)
    write_manifest(dest, entries)
    print(f"frozen: {len(entries)} files -> {dest.relative_to(ROOT).as_posix()}")
    return 0


def cmd_verify(version: str | None) -> int:
    version = version or latest_version()
    root = vault_dir(version)
    if not root.is_dir():
        print(f"MISSING: {root}", file=sys.stderr)
        return 2
    expected = read_manifest(root)
    actual = hash_tree(root)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    corrupt = sorted(r for r in set(expected) & set(actual) if expected[r] != actual[r])
    for rel in missing:
        print(f"MISSING  {rel}")
    for rel in extra:
        print(f"UNTRACKED {rel}")
    for rel in corrupt:
        print(f"CORRUPT  {rel}")
    if missing or extra or corrupt:
        print(
            f"vault {version}: FAIL "
            f"({len(missing)} missing, {len(extra)} untracked, {len(corrupt)} corrupt)",
            file=sys.stderr,
        )
        return 1
    print(f"vault {version}: OK ({len(expected)} files verified)")
    return 0


def cmd_diff(version: str | None) -> int:
    version = version or latest_version()
    root = vault_dir(version)
    if not root.is_dir():
        print(f"MISSING: {root}", file=sys.stderr)
        return 2
    vaulted = read_manifest(root)
    live = hash_tree(SPRITES)
    added = sorted(set(live) - set(vaulted))
    removed = sorted(set(vaulted) - set(live))
    changed = sorted(r for r in set(live) & set(vaulted) if live[r] != vaulted[r])
    for rel in added:
        print(f"ADDED    {rel}")
    for rel in removed:
        print(f"REMOVED  {rel}")
    for rel in changed:
        print(f"REVISED  {rel}")
    print(
        f"sprites/ vs vault {version}: "
        f"{len(changed)} revised, {len(added)} added, {len(removed)} removed, "
        f"{len(set(live) & set(vaulted)) - len(changed)} untouched"
    )
    # Drift is the expected state during an art round, so diff never fails the
    # build; only a *removed* file is a red flag worth a nonzero exit.
    return 1 if removed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_freeze = sub.add_parser("freeze", help="snapshot sprites/ into a new vault")
    p_freeze.add_argument("version", help="vault version tag, e.g. v2")
    for name in ("verify", "diff"):
        p = sub.add_parser(name)
        p.add_argument("--version", default=None, help="default: highest vault present")
    args = ap.parse_args(argv)
    if args.cmd == "freeze":
        return cmd_freeze(args.version)
    if args.cmd == "verify":
        return cmd_verify(args.version)
    return cmd_diff(args.version)


if __name__ == "__main__":
    raise SystemExit(main())
