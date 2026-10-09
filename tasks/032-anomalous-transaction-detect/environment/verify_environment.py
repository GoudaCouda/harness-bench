#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

parsed = datetime.fromisoformat("2026-08-19T15:00:00+00:00")
if parsed.astimezone(timezone.utc).isoformat() != "2026-08-19T15:00:00+00:00":
    raise SystemExit("timezone chronology probe failed")
if Decimal("75000.00") < Decimal("50000.00"):
    raise SystemExit("Decimal threshold probe failed")
if next(csv.DictReader(io.StringIO("id,status\nP-1,held\n"))) != {"id": "P-1", "status": "held"}:
    raise SystemExit("CSV graph probe failed")

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    state = root / "state.json"
    pending = root / ".state.pending"
    pending.write_text(json.dumps({"phase": "review_applied"}), encoding="utf-8")
    os.replace(pending, state)
    value = json.loads(state.read_text(encoding="utf-8"))
if value != {"phase": "review_applied"}:
    raise SystemExit("atomic local-state replacement probe failed")

print(json.dumps({"python3": "3.12", "csv_decimal_time": "passed", "atomic_replace": "passed"}, sort_keys=True))
