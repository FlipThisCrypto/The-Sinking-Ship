# SPDX-License-Identifier: MIT
"""Hygiene script: secret path patterns and clean-tree scan."""
from __future__ import annotations

import scripts.check_no_secrets as mod


def test_forbidden_name_matches_salt_and_pem():
    assert mod.FORBIDDEN_NAME.search("secrets/mint.salt")
    assert mod.FORBIDDEN_NAME.search("foo.salt")
    assert mod.FORBIDDEN_NAME.search("ops/server.pem")
    assert mod.FORBIDDEN_NAME.search("id_rsa")
    assert not mod.FORBIDDEN_NAME.search("engine/fulfillment/sources.py")
    assert not mod.FORBIDDEN_NAME.search("docs/LAUNCH-CHECKLIST.md")


def test_check_no_secrets_passes_on_this_repo():
    assert mod.main() == 0
