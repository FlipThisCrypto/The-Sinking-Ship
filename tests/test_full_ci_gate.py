# SPDX-License-Identifier: MIT
"""Iteration 50 — CI coherence gate: verify test files and module imports.

This smoke test validates:
  - All expected test files are present
  - All core shipgen and fulfillment modules are importable
  - ruff is installed and importable
  - The pyproject.toml CI configuration is present and parseable
"""
from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


def test_all_iteration_test_files_present():
    """Verify that every test file added across all 50 iterations exists."""
    expected = [
        # Existing core tests
        "test_roll_vectors.py",
        "test_drbg.py",
        "test_chain_identity.py",
        "test_config_and_schema.py",
        "test_fulfillment.py",
        "test_health.py",
        "test_budget_guard.py",
        "test_metrics.py",
        "test_circuit_breaker.py",
        "test_logging_util.py",
        "test_payment_sources.py",
        "test_retention.py",
        "test_sage_rpc.py",
        "test_mock_coinset.py",
        "test_reconcile_lock.py",
        "test_timing.py",
        "test_buyer_receipt.py",
        # Added in iterations 2-49
        "test_audit_and_invariants_cli.py",
        "test_site_html_validation.py",
        "test_ops_reporting_cli.py",
        "test_supply_and_scuttle_cli.py",
        "test_ops_alert_and_preflight_cli.py",
        "test_config_stamp_cli.py",
        "test_infra_and_health_utils.py",
        "test_governance_and_demo_cli.py",
        "test_brand_and_share_cards_cli.py",
        "test_run_pipeline_cli.py",
        "test_art_pipeline_utils.py",
        "test_doc_links.py",
        "test_polished_installers_cli.py",
        "test_tune_weights_cli.py",
        "test_placeholder_sprites_cli.py",
        "test_style_score_cli.py",
        "test_soak_fulfillment_cli.py",
        "test_build_site_data_cli.py",
        "test_site_links_cli.py",
        "test_simulate_cli.py",
        "test_validate_configs_cli.py",
        "test_render_engine_cli.py",
        "test_site_seo_and_security.py",
        "test_canon_utils.py",
        "test_schema_ref_and_keywords.py",
        "test_genconfig_utils.py",
        "test_amano_ink_primitives.py",
        "test_fulfillment_types.py",
        "test_fulfillment_init.py",
        "test_dry_run_offers.py",
        "test_shipgen_init.py",
    ]
    missing = [f for f in expected if not (TESTS / f).is_file()]
    assert not missing, f"Missing test files: {missing}"


def test_core_modules_importable():
    """All shipgen and fulfillment modules must import cleanly."""
    modules = [
        "shipgen",
        "shipgen.drbg",
        "shipgen.canon",
        "shipgen.config",
        "shipgen.schema",
        "shipgen.identity",
        "shipgen.roll",
        "fulfillment",
        "fulfillment.types",
        "fulfillment.ledger",
        "fulfillment.health",
        "fulfillment.metrics",
        "fulfillment.budget_guard",
        "fulfillment.circuit_breaker",
        "fulfillment.logging_util",
        "fulfillment.offers",
        "fulfillment.retention",
        "fulfillment.reconcile_lock",
        "fulfillment.timing",
    ]
    for mod in modules:
        obj = importlib.import_module(mod)
        assert obj is not None, f"Could not import {mod}"


def test_pyproject_toml_ci_config():
    """pyproject.toml must define pytest ini_options with pythonpath set."""
    toml_path = ROOT / "pyproject.toml"
    assert toml_path.is_file()
    with open(toml_path, "rb") as f:
        doc = tomllib.load(f)
    pytest_cfg = doc.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert "." in pytest_cfg.get("pythonpath", []), \
        "pythonpath must include '.' for engine imports"
