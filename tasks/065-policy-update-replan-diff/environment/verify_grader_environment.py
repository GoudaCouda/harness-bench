#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

stamp = datetime.fromisoformat("2026-09-02T07:30:00+00:00")
if stamp.tzinfo is None or stamp + timedelta(minutes=30) != datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc):
    raise SystemExit("grader timezone-aware datetime arithmetic probe failed")

rows = list(csv.DictReader(io.StringIO("decision_id,region\nD-001,AMER\n")))
if rows != [{"decision_id": "D-001", "region": "AMER"}]:
    raise SystemExit("grader CSV parsing probe failed")

probe = subprocess.run(
    [sys.executable, "-B", "-c", "import json; print(json.dumps({'ok': True}))"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or json.loads(probe.stdout) != {"ok": True}:
    raise SystemExit(f"grader subprocess probe failed: {probe.stdout!r} {probe.stderr!r}")

print(json.dumps({"python3": "3.10", "datetime": "passed", "csv": "passed", "subprocess": "passed"}, sort_keys=True))
