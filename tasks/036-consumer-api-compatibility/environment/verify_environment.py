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

baseline = {"required": {"id"}, "properties": {"id", "name"}}
candidate = {"required": {"id", "tenant"}, "properties": {"id", "name", "tenant"}}
if candidate["required"] - baseline["required"] != {"tenant"}:
    raise SystemExit("directional schema-set probe failed")

print(json.dumps({"python": "3.12", "unittest": "stdlib", "schema_sets": "passed"}, sort_keys=True))
