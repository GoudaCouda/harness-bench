#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

stamp = datetime.fromisoformat("2026-09-02T09:30:00+02:00")
if stamp.tzinfo is None or stamp + timedelta(hours=2) != datetime(2026, 9, 2, 11, 30, tzinfo=timezone(timedelta(hours=2))):
    raise SystemExit("timezone-aware datetime arithmetic probe failed")

rows = list(csv.DictReader(io.StringIO("region,exposure\nAMER,1420\nEU,1180\n")))
if rows != [{"region": "AMER", "exposure": "1420"}, {"region": "EU", "exposure": "1180"}]:
    raise SystemExit("CSV parsing probe failed")

probe = subprocess.run(
    [sys.executable, "-B", "-c", "import json; print(json.dumps({'ok': True}))"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or json.loads(probe.stdout) != {"ok": True}:
    raise SystemExit(f"python3 -B subprocess probe failed: {probe.stdout!r} {probe.stderr!r}")

print(json.dumps({"python3": "3.12", "datetime": "passed", "csv": "passed", "subprocess": "passed"}, sort_keys=True))
