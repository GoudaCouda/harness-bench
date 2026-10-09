#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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

digest = "sha256=" + "a" * 64
path = "demo_pkg/data.json"
if re.fullmatch(r"sha256=[0-9a-f]{64}", digest) is None:
    raise SystemExit("wheel RECORD digest probe failed")
if path.startswith("/") or ".." in path.split("/"):
    raise SystemExit("wheel RECORD relative-path probe failed")
actions = list(reversed(["write-a", "write-b", "write-c"]))
print(json.dumps({"python": "3.12", "reverse_actions": actions}, sort_keys=True))
