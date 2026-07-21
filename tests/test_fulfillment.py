# SPDX-License-Identifier: MIT
"""P7 fulfillment: ledger idempotency, crash-resume, budget refusal."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from fulfillment import (
    DryRunOfferBuilder,
    FixturePaymentSource,
    FulfillmentDaemon,
    PaymentState,
    SqliteLedger,
    TierPurchase,
    load_minting_defaults,
)
from shipgen.config import GenConfig
from shipgen.drbg import normalize_coin_id

TEST_SALT = b"fulfillment-test-salt-NOT-MAINNET-01"


def coin(n: int) -> str:
    return hashlib.sha256(f"fulfill-coin:{n}".encode()).hexdigest()


@pytest.fixture()
def cfg():
    return GenConfig()


@pytest.fixture()
def caps(cfg):
    return {t["name"]: t["passes"] for t in cfg.tiers_doc["tiers"]}


@pytest.fixture()
def ledger(tmp_path, caps):
    db = SqliteLedger(tmp_path / "ledger.sqlite", caps)
    yield db
    db.close()


def test_record_purchase_idempotent(ledger):
    p = TierPurchase(coin(1), "castaway", "xch1buyer", 10, "testnet11")
    a = ledger.record_purchase(p)
    b = ledger.record_purchase(p)
    assert a == b == 1


def test_status_summary_reports_integrity_and_path(ledger):
    s = ledger.status_summary()
    assert s["integrity_ok"] is True
    assert s["total_purchases"] == 0
    assert "ledger.sqlite" in s["db_path"].replace("\\", "/")


def test_cli_backup_creates_integrity_ok_copy(tmp_path, ledger, monkeypatch):
    import fulfillment_daemon as fd

    ledger.record_purchase(
        TierPurchase(coin(77), "castaway", "xch1buyer", 1, "testnet11"))
    src = Path(ledger.path)
    ledger.close()
    dest = tmp_path / "backup" / "ledger.sqlite"
    monkeypatch.setattr(
        "sys.argv",
        ["fulfillment_daemon.py", "backup", "--db", str(src), "--out", str(dest)],
    )
    assert fd.main() == 0
    assert dest.is_file()
    from fulfillment import SqliteLedger
    from shipgen.config import GenConfig
    caps = {t["name"]: t["passes"] for t in GenConfig().tiers_doc["tiers"]}
    b = SqliteLedger(dest, caps)
    try:
        assert b.integrity_ok()
        assert b.status_summary()["total_purchases"] == 1
    finally:
        b.close()


def test_ordinals_increment_per_tier(ledger):
    for i in range(3):
        o = ledger.record_purchase(
            TierPurchase(coin(100 + i), "castaway", "xch1b", i + 1, "testnet11"))
        assert o == i + 1


def test_double_fulfill_same_manifest(tmp_path, ledger, cfg):
    """Crash-resume: second tick must not change the stored manifest hash."""
    c = coin(7)
    fixture = tmp_path / "pay.json"
    fixture.write_text(json.dumps([{
        "coin_id": c,
        "tier_name": "castaway",
        "buyer_address": "xch1buyer",
        "block_height": 5,
        "network": "testnet11",
    }]), encoding="utf-8")

    daemon = FulfillmentDaemon(
        source=FixturePaymentSource(fixture),
        ledger=ledger,
        offers=DryRunOfferBuilder(),
        salt=TEST_SALT,
        cfg=cfg,
        manifest_outdir=tmp_path / "chests",
        metadata_outdir=tmp_path / "meta",
    )
    s1 = daemon.tick(dry_run=False)
    assert s1["fulfilled"] == 1
    assert not s1["errors"]
    h1 = ledger.get_manifest(c)["manifest_hash"]

    s2 = daemon.tick(dry_run=False)
    assert s2["fulfilled"] == 0  # already fulfilled
    assert ledger.get_manifest(c)["manifest_hash"] == h1
    assert ledger.state_of(c) == PaymentState.FULFILLED


def test_reveal_outdir_publishes_offer_json(tmp_path, ledger, cfg):
    c = coin(88)
    fixture = tmp_path / "pay.json"
    fixture.write_text(json.dumps([{
        "coin_id": c,
        "tier_name": "castaway",
        "buyer_address": "xch1buyer",
        "block_height": 5,
        "network": "testnet11",
    }]), encoding="utf-8")
    reveal = tmp_path / "site_chests"
    daemon = FulfillmentDaemon(
        source=FixturePaymentSource(fixture),
        ledger=ledger,
        offers=DryRunOfferBuilder(),
        salt=TEST_SALT,
        cfg=cfg,
        manifest_outdir=tmp_path / "chests",
        metadata_outdir=tmp_path / "meta",
        reveal_outdir=reveal,
    )
    assert daemon.tick(dry_run=False)["fulfilled"] == 1
    published = list(reveal.glob("*.json"))
    assert len(published) == 1
    doc = json.loads(published[0].read_text(encoding="utf-8"))
    assert doc["schema"] == "chest-manifest-v1"
    assert doc["manifest_hash"] == ledger.get_manifest(c)["manifest_hash"]


def test_budget_refusal(tmp_path, cfg, caps):
    """When budget is already exhausted, confirmed purchase is refused."""
    ledger = SqliteLedger(tmp_path / "budget.sqlite", caps)
    # Force next start and consume budget by rolling a real chest then
    # manually setting quantity sum via a tiny hack: lower budget on daemon.
    c = coin(9)
    fixture = tmp_path / "pay.json"
    fixture.write_text(json.dumps([{
        "coin_id": c,
        "tier_name": "castaway",
        "buyer_address": "xch1buyer",
        "block_height": 1,
        "network": "testnet11",
    }]), encoding="utf-8")

    daemon = FulfillmentDaemon(
        source=FixturePaymentSource(fixture),
        ledger=ledger,
        offers=DryRunOfferBuilder(),
        salt=TEST_SALT,
        cfg=cfg,
        manifest_outdir=tmp_path / "chests",
        metadata_outdir=tmp_path / "meta",
    )
    daemon.budget = 0  # nothing left for public mint
    s = daemon.tick(dry_run=False)
    assert s["refused"] == 1
    assert ledger.state_of(c) == PaymentState.REFUSED
    assert ledger.get_manifest(c) is None
    ledger.close()


def test_fixture_normalizes_coin_id(tmp_path):
    c = coin(3)
    path = tmp_path / "f.json"
    path.write_text(json.dumps([{
        "coin_id": "0x" + c.upper(),
        "tier_name": "snorkeler",
        "buyer_address": "xch1x",
        "block_height": 2,
    }]), encoding="utf-8")
    src = FixturePaymentSource(path)
    got = src.poll_confirmed(0)
    assert len(got) == 1
    assert got[0].coin_id == normalize_coin_id(c)


def test_roll_resume_without_refulfill_partial(tmp_path, ledger, cfg):
    """If ROLLED but not FULFILLED, re-tick completes with same manifest."""
    c = coin(11)
    ledger.record_purchase(
        TierPurchase(c, "castaway", "xch1buyer", 1, "testnet11"))
    daemon = FulfillmentDaemon(
        source=FixturePaymentSource(_empty_fixture(tmp_path)),
        ledger=ledger,
        offers=DryRunOfferBuilder(),
        salt=TEST_SALT,
        cfg=cfg,
        manifest_outdir=tmp_path / "chests",
        metadata_outdir=tmp_path / "meta",
    )
    # First: force roll only by calling internal path twice
    r1 = daemon._fulfill_one(c, dry_run=False)
    assert r1 == "fulfilled"
    h = ledger.get_manifest(c)["manifest_hash"]
    # Simulate crashed state: set back to ROLLED with same manifest
    ledger._conn.execute(
        "UPDATE purchases SET state = 'rolled', offer_id = NULL WHERE coin_id = ?",
        (c,),
    )
    r2 = daemon._fulfill_one(c, dry_run=False)
    assert r2 == "fulfilled"
    assert ledger.get_manifest(c)["manifest_hash"] == h


def _empty_fixture(tmp_path: Path) -> Path:
    p = tmp_path / "empty.json"
    p.write_text("[]", encoding="utf-8")
    return p


def test_daemon_minting_defaults_match_collection_json(tmp_path, ledger, cfg):
    """Royalty/DID for mint must match metadata_gen's collection.json source."""
    minting = load_minting_defaults()
    daemon = FulfillmentDaemon(
        source=FixturePaymentSource(_empty_fixture(tmp_path)),
        ledger=ledger,
        offers=DryRunOfferBuilder(),
        salt=TEST_SALT,
        cfg=cfg,
        manifest_outdir=tmp_path / "chests",
        metadata_outdir=tmp_path / "meta",
    )
    assert daemon.royalty_basis_points == int(
        minting["royalty_percentage_basis_points"]
    )
    assert daemon.did == minting["did"]
    # Guard against the old hardcoded 300 bp default drifting from config.
    assert daemon.royalty_basis_points == 500


def test_daemon_minting_overrides_respected(tmp_path, ledger, cfg):
    daemon = FulfillmentDaemon(
        source=FixturePaymentSource(_empty_fixture(tmp_path)),
        ledger=ledger,
        offers=DryRunOfferBuilder(),
        salt=TEST_SALT,
        cfg=cfg,
        did="did:chia:override-test",
        royalty_basis_points=100,
        manifest_outdir=tmp_path / "chests",
        metadata_outdir=tmp_path / "meta",
    )
    assert daemon.did == "did:chia:override-test"
    assert daemon.royalty_basis_points == 100


def test_cli_refuses_mainnet_without_allow_flag(tmp_path, monkeypatch):
    """Live mainnet tick/reconcile must not run by accident."""
    import fulfillment_daemon as fd

    salt = tmp_path / "t.salt"
    salt.write_bytes(b"x" * 16)
    fixture = tmp_path / "empty.json"
    fixture.write_text("[]", encoding="utf-8")
    db = str(tmp_path / "l.sqlite")

    def run(argv: list[str]) -> int:
        monkeypatch.setattr(
            "sys.argv",
            ["fulfillment_daemon.py"] + argv,
        )
        return fd.main()

    code = run([
        "tick", "--fixture", str(fixture), "--salt-file", str(salt),
        "--db", db, "--network", "mainnet",
    ])
    assert code == 2

    code = run([
        "reconcile", "--fixture", str(fixture), "--salt-file", str(salt),
        "--db", db, "--network", "mainnet", "--loops", "1",
    ])
    assert code == 2

    # dry-run still allowed for dress rehearsal
    code = run([
        "tick", "--fixture", str(fixture), "--salt-file", str(salt),
        "--db", db, "--network", "mainnet", "--dry-run",
    ])
    assert code == 0


def test_export_audit_includes_fulfillment_actions(tmp_path, ledger, cfg):
    """Incident recovery: audit trail must record purchase + fulfill events."""
    c = coin(42)
    fixture = tmp_path / "pay.json"
    fixture.write_text(json.dumps([{
        "coin_id": c,
        "tier_name": "castaway",
        "buyer_address": "xch1buyer",
        "block_height": 5,
        "network": "testnet11",
    }]), encoding="utf-8")
    daemon = FulfillmentDaemon(
        source=FixturePaymentSource(fixture),
        ledger=ledger,
        offers=DryRunOfferBuilder(),
        salt=TEST_SALT,
        cfg=cfg,
        manifest_outdir=tmp_path / "chests",
        metadata_outdir=tmp_path / "meta",
    )
    summary = daemon.tick(dry_run=False)
    assert summary["fulfilled"] == 1
    audit = ledger.export_audit()
    assert len(audit) >= 1
    actions = {row["action"] for row in audit}
    # At least one action tied to this coin appears in the append-only log.
    coins = {row.get("coin_id") for row in audit}
    assert c in coins or any(c[:12] in str(row) for row in audit)
    assert actions, "expected non-empty audit actions after fulfill"
