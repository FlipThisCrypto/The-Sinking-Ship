# SPDX-License-Identifier: MIT
"""Structured JSON logging for fulfillment ops."""
from __future__ import annotations

import json
import logging

from fulfillment.logging_util import JsonLineFormatter, configure_logging, event


def test_json_line_formatter_includes_level_and_msg():
    fmt = JsonLineFormatter()
    record = logging.LogRecord(
        name="fulfillment.daemon",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="tick done",
        args=(),
        exc_info=None,
    )
    record.event = "tick_complete"
    record.fulfilled = 2
    line = fmt.format(record)
    doc = json.loads(line)
    assert doc["level"] == "INFO"
    assert doc["msg"] == "tick done"
    assert doc["event"] == "tick_complete"
    assert doc["fulfilled"] == 2
    assert "ts" in doc


def test_configure_logging_json_mode(capsys):
    configure_logging(json_logs=True)
    log = logging.getLogger("fulfillment.test")
    event(log, "unit_probe", ok=True)
    err = capsys.readouterr().err.strip().splitlines()[-1]
    doc = json.loads(err)
    assert doc["event"] == "unit_probe"
    assert doc["ok"] is True
