#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from collections import defaultdict

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
python = shutil.which("python")
if not python:
    raise SystemExit("task verification command requires the python alias")
version = subprocess.run(
    [python, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if version.returncode != 0 or version.stdout.strip() != "3.12":
    raise SystemExit(f"python alias probe failed: {version.stdout!r} {version.stderr!r}")

events = [{"event_id": "late-1", "key": "acct", "event_ms": -1, "value": 2}]
original = copy.deepcopy(events)
windows = defaultdict(list)
for event in events:
    windows[(event["event_ms"] // 50) * 50].append(event["event_id"])
if dict(windows) != {-50: ["late-1"]} or events != original:
    raise SystemExit("event-time floor-division or input-immutability probe failed")

print(json.dumps({"python": "3.12", "event_time": "passed", "copy_collections": "passed"}, sort_keys=True))
