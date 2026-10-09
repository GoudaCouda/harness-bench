#!/usr/bin/env python3
from __future__ import annotations

import itertools
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

combinations = list(itertools.combinations(("1.1.0", "1.2.0", "2.0.0"), 2))
if combinations[0] != ("1.1.0", "1.2.0") or len(combinations) != 3:
    raise SystemExit("bounded dependency search probe failed")

print(json.dumps({"python": "3.12", "itertools": "passed", "unittest": "stdlib"}, sort_keys=True))
