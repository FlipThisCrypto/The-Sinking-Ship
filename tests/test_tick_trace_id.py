# SPDX-License-Identifier: MIT
"""Round 2 Iteration 1: verify tick trace_id correlation in structured log events."""
from __future__ import annotations

import json
import logging
from pathlib import Path


from fulfillment.daemon import FulfillmentDaemon
from fulfillment.ledger import SqliteLedger
from fulfillment.logging_util import JsonLineFormatter
from fulfillment.offers import DryRunOfferBuilder
from fulfillment.sources import FixturePaymentSource


FIXTURE = Path(__file__).parent.parent / "fixtures" / "example_payments.json"
SALT = b"\xde\xad\xbe\xef" * 8  # 32 bytes for testing


def _make_daemon(tmp_path: Path) -> FulfillmentDaemon:
    ledger = SqliteLedger(
        tmp_path / "ledger.sqlite",
        tier_pass_caps={"castaway": 10, "survivor": 5,
                        "first_mate": 3, "submarine_captain": 2},
    )
    source = FixturePaymentSource(FIXTURE)
    offers = DryRunOfferBuilder()
    return FulfillmentDaemon(
        source=source,
        ledger=ledger,
        offers=offers,
        salt=SALT,
        network="testnet11",
    )


def test_tick_summary_contains_trace_id(tmp_path):
    daemon = _make_daemon(tmp_path)
    summary = daemon.tick(dry_run=True)
    assert "trace_id" in summary
    tid = summary["trace_id"]
    assert isinstance(tid, str)
    # UUID4: 36 chars, 4 hyphens, 5 segments
    parts = tid.split("-")
    assert len(parts) == 5, f"trace_id not UUID4 format: {tid}"


def test_trace_id_unique_per_tick(tmp_path):
    daemon = _make_daemon(tmp_path)
    s1 = daemon.tick(dry_run=True)
    s2 = daemon.tick(dry_run=True)
    assert s1["trace_id"] != s2["trace_id"], "each tick must produce a distinct trace_id"


def test_trace_id_in_structured_log_events(tmp_path, caplog):
    """All JSON-line events within a tick must carry the same trace_id."""
    daemon = _make_daemon(tmp_path)

    records: list[logging.LogRecord] = []

    class CapturingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = CapturingHandler()
    handler.setFormatter(JsonLineFormatter())
    log = logging.getLogger("fulfillment.daemon")
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    try:
        summary = daemon.tick(dry_run=True)
    finally:
        log.removeHandler(handler)

    trace_id = summary["trace_id"]
    assert trace_id, "trace_id must be non-empty"

    # Parse every JSON log line emitted by the daemon
    json_events = []
    for record in records:
        try:
            line = handler.format(record)
            doc = json.loads(line)
            json_events.append(doc)
        except (ValueError, TypeError):
            pass

    # tick_start and tick_complete must be present and carry trace_id
    events_by_name = {d.get("event"): d for d in json_events}
    assert "tick_start" in events_by_name, "tick_start event missing"
    assert "tick_complete" in events_by_name, "tick_complete event missing"
    assert events_by_name["tick_start"].get("trace_id") == trace_id
    assert events_by_name["tick_complete"].get("trace_id") == trace_id

    # Any fulfill_one events must also carry the same trace_id
    fulfill_events = [d for d in json_events if d.get("event") == "fulfill_one"]
    for fe in fulfill_events:
        assert fe.get("trace_id") == trace_id, (
            f"fulfill_one event missing matching trace_id: {fe}"
        )
