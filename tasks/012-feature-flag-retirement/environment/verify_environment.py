#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

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

def parse_wire(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError(value)
    return parsed.replace(tzinfo=timezone.utc)

historical = parse_wire("2026-05-31T23:59:59Z")
cutoff = parse_wire("2026-06-01T00:00:00Z")
if not historical < cutoff:
    raise SystemExit("event-time cutoff comparison probe failed")
try:
    parse_wire("2026-02-30T00:00:00Z")
except ValueError:
    pass
else:
    raise SystemExit("invalid calendar date was accepted")
print(json.dumps({"python": "3.12", "strict_utc_datetime": "passed"}, sort_keys=True))
