#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    output = root / "normalized"
    output.mkdir()
    source_rows = list(csv.DictReader(io.StringIO(
        "id,name,email,status\nC-001,Ada,ada@example.test,active\n"
    )))
    record = {
        "record_id": source_rows[0]["id"],
        "record_type": "customer",
        "name": source_rows[0]["name"],
        "email": source_rows[0]["email"],
        "status": source_rows[0]["status"],
    }
    target = output / f"customer_{record['record_id']}.json"
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    pending = root / ".record.pending"
    pending.write_text(payload, encoding="utf-8")
    os.replace(pending, target)
    before = target.read_bytes()
    pending.write_text(payload, encoding="utf-8")
    os.replace(pending, target)
    if target.read_bytes() != before or set(json.loads(target.read_text())) != set(record):
        raise SystemExit("deterministic normalization replay probe failed")

print(json.dumps({"python3": "3.12", "csv_json": "passed", "idempotent_replay": "passed"}, sort_keys=True))
