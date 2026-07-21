# SPDX-License-Identifier: MIT
from fulfillment.timing import timed_section
import time
def test_timed_section_runs():
    with timed_section("unit", warn_ms=99999):
        time.sleep(0.001)
