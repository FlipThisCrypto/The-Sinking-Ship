# SPDX-License-Identifier: MIT
"""End-to-end CLI behavior: commit -> roll -> verify, plus tamper detection."""
import json
import sys

import pytest

import chest_roller
from conftest import TEST_SALT, COIN_A


@pytest.fixture()
def salt_file(tmp_path):
    p = tmp_path / "test.salt"
    p.write_bytes(TEST_SALT)
    return str(p)


def run_cli(argv) -> int:
    old = sys.argv
    sys.argv = ["chest_roller.py"] + argv
    try:
        return chest_roller.main()
    finally:
        sys.argv = old


def test_commit_roll_verify_roundtrip(tmp_path, salt_file):
    outdir = tmp_path / "out"
    assert run_cli(["commit", "--salt-file", salt_file,
                    "--outdir", str(outdir / "commitment")]) == 0
    hash_txt = (outdir / "commitment" / "commitment_hash.txt").read_text().strip()
    assert len(hash_txt) == 64

    assert run_cli(["roll", "--tier", "shipwright", "--coin-id", "0x" + COIN_A,
                    "--salt-file", salt_file, "--pass-ordinal", "3",
                    "--start-index", "777", "--outdir", str(outdir / "chests")]) == 0
    manifest_path = outdir / "chests" / f"chest_shipwright_{COIN_A[:8]}.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["provenance_commitment"] == hash_txt

    assert run_cli(["verify", "--manifest", str(manifest_path),
                    "--salt-file", salt_file]) == 0


def test_verify_detects_tampering(tmp_path, salt_file):
    outdir = tmp_path / "chests"
    run_cli(["roll", "--tier", "snorkeler", "--coin-id", COIN_A,
             "--salt-file", salt_file, "--pass-ordinal", "1",
             "--start-index", "1", "--outdir", str(outdir)])
    path = outdir / f"chest_snorkeler_{COIN_A[:8]}.json"
    doc = json.loads(path.read_text())
    for e in doc["nfts"]:
        if e["type"] == "generated":
            e["rarity_tier"] = "mythic"  # the classic grift
            break
    path.write_text(json.dumps(doc, indent=2, sort_keys=True))
    assert run_cli(["verify", "--manifest", str(path),
                    "--salt-file", salt_file]) == 1


def test_verify_fails_with_wrong_salt(tmp_path, salt_file):
    outdir = tmp_path / "chests"
    run_cli(["roll", "--tier", "snorkeler", "--coin-id", COIN_A,
             "--salt-file", salt_file, "--pass-ordinal", "1",
             "--start-index", "1", "--outdir", str(outdir)])
    wrong = tmp_path / "wrong.salt"
    wrong.write_bytes(b"completely-different-salt-000001")
    assert run_cli(["verify",
                    "--manifest", str(outdir / f"chest_snorkeler_{COIN_A[:8]}.json"),
                    "--salt-file", str(wrong)]) == 1


def test_roll_rejects_bad_inputs(salt_file, tmp_path):
    with pytest.raises(ValueError):
        run_cli(["roll", "--tier", "not_a_tier", "--coin-id", COIN_A,
                 "--salt-file", salt_file, "--pass-ordinal", "1",
                 "--start-index", "1", "--outdir", str(tmp_path)])
    with pytest.raises(ValueError):
        run_cli(["roll", "--tier", "admiral", "--coin-id", COIN_A,
                 "--salt-file", salt_file, "--pass-ordinal", "99",
                 "--start-index", "1", "--outdir", str(tmp_path)])
    with pytest.raises(ValueError):
        run_cli(["roll", "--tier", "admiral", "--coin-id", "nothex",
                 "--salt-file", salt_file, "--pass-ordinal", "1",
                 "--start-index", "1", "--outdir", str(tmp_path)])
