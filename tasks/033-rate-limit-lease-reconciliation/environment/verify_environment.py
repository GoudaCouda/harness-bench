#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

alias = subprocess.run(
    ["python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    capture_output=True,
    text=True,
    check=False,
    timeout=10,
)
if alias.returncode != 0 or alias.stdout.strip() != "3.12":
    raise SystemExit(f"python alias mismatch: {alias.stdout!r} {alias.stderr!r}")

sample = sorted([{"requested_ms": 2, "request_id": "b"}, {"requested_ms": 1, "request_id": "a"}], key=lambda row: (row["requested_ms"], row["request_id"]))
if [row["request_id"] for row in sample] != ["a", "b"]:
    raise SystemExit("deterministic FIFO ordering probe failed")

print(json.dumps({"python": "3.12", "unittest": "stdlib", "fifo_sort": "passed"}, sort_keys=True))
