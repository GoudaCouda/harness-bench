#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

rows = list(csv.DictReader(io.StringIO("path,action\nstaging/part.csv,purge\n")))
if rows != [{"path": "staging/part.csv", "action": "purge"}]:
    raise SystemExit("cleanup-plan CSV probe failed")

with tempfile.TemporaryDirectory() as temporary:
    artifact = Path(temporary) / "staged.jsonl"
    artifact.write_text('{"row":1}\n', encoding="utf-8")
    artifact.unlink()
    if artifact.exists():
        raise SystemExit("workspace purge probe failed")

events = [json.loads(line) for line in '{"event_id":"AUD-1"}\n{"event_id":"AUD-2"}\n'.splitlines()]
if [event["event_id"] for event in events] != ["AUD-1", "AUD-2"]:
    raise SystemExit("append-only audit JSONL probe failed")

print(json.dumps({"python3": "3.12", "cleanup_csv": "passed", "purge": "passed", "jsonl": "passed"}, sort_keys=True))
