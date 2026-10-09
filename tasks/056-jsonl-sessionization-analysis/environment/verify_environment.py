#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import datetime, timezone, timedelta

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

jsonl = (
    '{"event_id":"E1","timestamp":"2026-04-10T09:00:00Z","event_type":"page_view"}\n'
    '{"event_id":"E2","timestamp":"2026-04-10T09:30:00Z","event_type":"purchase"}\n'
)
events = [json.loads(line) for line in jsonl.splitlines()]
times = [
    datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).astimezone(timezone.utc)
    for event in events
]
rows = list(csv.DictReader(io.StringIO("raw_campaign,canonical_source\ngclid,google\n")))
if (
    times[1] - times[0] != timedelta(minutes=30)
    or rows != [{"raw_campaign": "gclid", "canonical_source": "google"}]
):
    raise SystemExit("JSONL session boundary or campaign mapping probe failed")

print(json.dumps({"python3": "3.12", "jsonl_time": "passed", "csv_mapping": "passed"}, sort_keys=True))
