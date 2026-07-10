# SPDX-License-Identifier: MIT
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest  # noqa: E402

from shipgen.config import GenConfig  # noqa: E402
from shipgen.roll import RollEngine, derive_placements, build_commitment  # noqa: E402

TEST_SALT = b"test-salt-for-the-sinking-ship-0001"
COIN_A = "aa" * 32
COIN_B = "bb" * 32


@pytest.fixture(scope="session")
def cfg():
    return GenConfig()


@pytest.fixture(scope="session")
def engine(cfg):
    return RollEngine(cfg)


@pytest.fixture(scope="session")
def placements(cfg):
    return derive_placements(TEST_SALT, cfg)


@pytest.fixture(scope="session")
def commitment(cfg):
    return build_commitment(TEST_SALT, cfg)
