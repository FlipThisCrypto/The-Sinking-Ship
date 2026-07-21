# SPDX-License-Identifier: MIT
from pathlib import Path
from fulfillment.ci_hooks import ROUND3_REQUIRED_CI_SCRIPTS
def test_required_scripts_exist():
    root = Path(__file__).resolve().parent.parent
    for rel in ROUND3_REQUIRED_CI_SCRIPTS:
        assert (root / rel).is_file(), rel
