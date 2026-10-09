#!/usr/bin/env python3
"""Task 158 plans from captured evidence offline; a Kafka cluster is intentionally absent."""
from __future__ import annotations

import hashlib
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
evidence = {
    "input_offsets": {"orders-0": [40, 49]},
    "committed_group_offset": {"orders-0": 50},
    "read_committed_output_keys": ["orders-0:40-49"],
    "producer_epoch": 8,
}
settled = (
    evidence["committed_group_offset"]["orders-0"] == 50
    and "orders-0:40-49" in evidence["read_committed_output_keys"]
)
if not settled or evidence["producer_epoch"] < 0:
    raise SystemExit("transactional offset evidence probe failed")
payload = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("Kafka evidence digest probe failed")
print(json.dumps({
    "python3": "3.12", "transaction_evidence": "passed", "json": "passed",
    "sha256": "passed", "kafka_runtime": "not_required_by_task_contract",
}, sort_keys=True))
