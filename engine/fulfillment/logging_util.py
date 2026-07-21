# SPDX-License-Identifier: MIT
"""Structured logging helpers for fulfillment ops (alert-ready JSON lines)."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonLineFormatter(logging.Formatter):
    """Emit one JSON object per log record for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Extra fields attached via logger.info("...", extra={...}) when keys
        # do not collide with LogRecord attributes.
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "taskName", "message",
            }:
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_logging(*, json_logs: bool = False, level: int = logging.INFO) -> None:
    """Configure root handlers for fulfillment CLI processes."""
    root = logging.getLogger()
    # Avoid duplicate handlers if configure is called twice in tests.
    root.handlers.clear()
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stderr)
    if json_logs:
        handler.setFormatter(JsonLineFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    root.addHandler(handler)


def event(logger: logging.Logger, event_name: str, **fields: Any) -> None:
    """Log a named structured event (always includes event=)."""
    extra = {"event": event_name, **fields}
    logger.info(event_name, extra=extra)
