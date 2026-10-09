#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")


def sequencer_value(value: str) -> int:
    return int(value, 16)


if not (
    sequencer_value("f") == sequencer_value("0f")
    and sequencer_value("10") > sequencer_value("f")
):
    raise SystemExit("S3 sequencer comparison probe failed")

events = [
    {"key": "a.txt", "sequencer": "0f", "event_id": "e-1"},
    {"key": "b.txt", "sequencer": "02", "event_id": "e-2"},
    {"key": "a.txt", "sequencer": "10", "event_id": "e-3"},
]
checkpoints: dict[str, int] = {}
for event in events:
    current = checkpoints.get(event["key"], -1)
    value = sequencer_value(event["sequencer"])
    if value > current:
        checkpoints[event["key"]] = value
if checkpoints != {"a.txt": 16, "b.txt": 2}:
    raise SystemExit("per-key checkpoint probe failed")
fingerprint = hashlib.sha256(
    json.dumps(events[0], sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
print(json.dumps({"python3": "3.12", "sequencer": "passed", "checkpoints": "passed",
                  "fingerprint_length": len(fingerprint),
                  "aws_runtime": "not_required_by_task_contract"}, sort_keys=True))
