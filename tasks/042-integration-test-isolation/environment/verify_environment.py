#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

alias = subprocess.run(["python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], capture_output=True, text=True, check=False, timeout=10)
if alias.returncode != 0 or alias.stdout.strip() != "3.12":
    raise SystemExit(f"python alias mismatch: {alias.stdout!r} {alias.stderr!r}")

fixture = {"nested": {"items": []}}
first = copy.deepcopy(fixture)
second = copy.deepcopy(fixture)
first["nested"]["items"].append("changed")
if second != fixture or first == second:
    raise SystemExit("deep fixture isolation probe failed")
stable_seed = sum((index + 1) * byte for index, byte in enumerate(b"test-a"))
if stable_seed != 1934:
    raise SystemExit("stable identity probe failed")

print(json.dumps({"python": "3.12", "copy_deepcopy": "passed", "unittest": "stdlib"}, sort_keys=True))
