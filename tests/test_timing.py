# SPDX-License-Identifier: MIT
import time

from fulfillment.timing import timed_section


def test_timed_section_runs():
    with timed_section("unit", warn_ms=99999):
        time.sleep(0.001)


def test_timed_section_warns_on_slow(capsys):
    with timed_section("slow_test", warn_ms=0.001):
        time.sleep(0.01)
    captured = capsys.readouterr().out
    assert "WARN" in captured
    assert "slow_test" in captured
