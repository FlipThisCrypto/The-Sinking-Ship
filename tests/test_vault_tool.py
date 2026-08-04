# SPDX-License-Identifier: MIT
"""Tests for scripts/vault_tool.py and the integrity of vault/sprites-v1.

The vault is the only copy of the externally authored ``body/`` and
``ship_class/`` illustrations that is guaranteed not to be overwritten by an
art round, so its completeness is a repository invariant.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "vault_tool", ROOT / "scripts" / "vault_tool.py"
)
assert SPEC and SPEC.loader
vault_tool = importlib.util.module_from_spec(SPEC)
sys.modules["vault_tool"] = vault_tool
SPEC.loader.exec_module(vault_tool)

VAULT_V1 = ROOT / "vault" / "sprites-v1"


def test_vault_v1_exists_with_manifest():
    assert VAULT_V1.is_dir(), "vault/sprites-v1 is missing"
    assert (VAULT_V1 / vault_tool.MANIFEST_NAME).is_file()


def test_manifest_covers_every_vaulted_file():
    entries = vault_tool.read_manifest(VAULT_V1)
    on_disk = {
        p.relative_to(VAULT_V1).as_posix() for p in vault_tool.walk_tree(VAULT_V1)
    }
    assert entries.keys() == on_disk


def test_manifest_digests_are_sha256_hex():
    for rel, digest in vault_tool.read_manifest(VAULT_V1).items():
        assert len(digest) == 64, rel
        int(digest, 16)  # raises if not hex


def test_vault_holds_every_sprite_filename_traits_json_requires():
    """Every sprite the trait config names must have a vaulted original."""
    traits = json.loads((ROOT / "config" / "traits.json").read_text(encoding="utf-8"))
    entries = vault_tool.read_manifest(VAULT_V1)
    missing = []
    for layer in traits["layers"]:
        if layer["name"] == "body":
            continue  # composed via sprite_pattern, checked below
        for trait in layer["traits"]:
            fn = trait.get("sprite_filename")
            if fn and f"{layer['name']}/{fn}" not in entries:
                missing.append(f"{layer['name']}/{fn}")
    assert not missing, f"vault is missing originals: {missing}"


def test_vault_holds_all_48_body_sprites():
    entries = vault_tool.read_manifest(VAULT_V1)
    bodies = [k for k in entries if k.startswith("body/") and k.endswith(".png")]
    assert len(bodies) == 48, f"expected 48 body sprites, vault has {len(bodies)}"


def test_verify_passes_on_committed_vault():
    assert vault_tool.cmd_verify("v1") == 0


def test_verify_detects_corruption(tmp_path, monkeypatch):
    fake = tmp_path / "vault" / "sprites-v9"
    (fake / "sky").mkdir(parents=True)
    target = fake / "sky" / "a.png"
    target.write_bytes(b"original")
    vault_tool.write_manifest(fake, vault_tool.hash_tree(fake))
    monkeypatch.setattr(vault_tool, "VAULT", tmp_path / "vault")
    assert vault_tool.cmd_verify("v9") == 0
    target.write_bytes(b"tampered")
    assert vault_tool.cmd_verify("v9") == 1


def test_verify_detects_missing_file(tmp_path, monkeypatch):
    fake = tmp_path / "vault" / "sprites-v9"
    fake.mkdir(parents=True)
    (fake / "a.png").write_bytes(b"a")
    (fake / "b.png").write_bytes(b"b")
    vault_tool.write_manifest(fake, vault_tool.hash_tree(fake))
    monkeypatch.setattr(vault_tool, "VAULT", tmp_path / "vault")
    (fake / "b.png").unlink()
    assert vault_tool.cmd_verify("v9") == 1


def test_freeze_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT", tmp_path / "vault")
    (tmp_path / "vault" / "sprites-v9").mkdir(parents=True)
    assert vault_tool.cmd_freeze("v9") == 2


def test_latest_version_picks_highest_numerically(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT", tmp_path / "vault")
    for name in ("sprites-v1", "sprites-v2", "sprites-v10"):
        (tmp_path / "vault" / name).mkdir(parents=True)
    assert vault_tool.latest_version() == "v10"


def test_latest_version_raises_on_empty_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT", tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    with pytest.raises(FileNotFoundError):
        vault_tool.latest_version()


def test_diff_reports_removed_as_failure(tmp_path, monkeypatch):
    fake_vault = tmp_path / "vault" / "sprites-v9"
    fake_vault.mkdir(parents=True)
    (fake_vault / "a.png").write_bytes(b"a")
    (fake_vault / "gone.png").write_bytes(b"g")
    vault_tool.write_manifest(fake_vault, vault_tool.hash_tree(fake_vault))
    live = tmp_path / "sprites"
    live.mkdir()
    (live / "a.png").write_bytes(b"a")
    monkeypatch.setattr(vault_tool, "VAULT", tmp_path / "vault")
    monkeypatch.setattr(vault_tool, "SPRITES", live)
    assert vault_tool.cmd_diff("v9") == 1


def test_diff_tolerates_revised_art(tmp_path, monkeypatch):
    fake_vault = tmp_path / "vault" / "sprites-v9"
    fake_vault.mkdir(parents=True)
    (fake_vault / "a.png").write_bytes(b"old")
    vault_tool.write_manifest(fake_vault, vault_tool.hash_tree(fake_vault))
    live = tmp_path / "sprites"
    live.mkdir()
    (live / "a.png").write_bytes(b"new art")
    monkeypatch.setattr(vault_tool, "VAULT", tmp_path / "vault")
    monkeypatch.setattr(vault_tool, "SPRITES", live)
    assert vault_tool.cmd_diff("v9") == 0
