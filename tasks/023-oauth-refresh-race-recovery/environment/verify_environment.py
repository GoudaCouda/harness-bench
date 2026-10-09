#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
alias = subprocess.run(
    ["python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    capture_output=True, text=True, check=False, timeout=10,
)
if alias.returncode != 0 or alias.stdout.strip() != "3.12":
    raise SystemExit(f"python alias mismatch: {alias.stdout!r} {alias.stderr!r}")
attempts = [
    {"sequence": 2, "status": "success", "generation": 4},
    {"sequence": 1, "status": "transient_error", "generation": 4},
]
ordered = sorted(attempts, key=lambda row: row["sequence"])
if [row["sequence"] for row in ordered] != [1, 2]:
    raise SystemExit("refresh completion-order probe failed")
print(json.dumps({"python": "3.12", "ordered_attempts": ordered}, sort_keys=True))
