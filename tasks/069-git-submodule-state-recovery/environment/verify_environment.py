#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

python = shutil.which("python")
if not python:
    raise SystemExit("published verification command requires the python alias")
probe = subprocess.run(
    [python, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "3.12":
    raise SystemExit(f"python alias probe failed: {probe.stdout!r} {probe.stderr!r}")
if unittest.defaultTestLoader is None:
    raise SystemExit("unittest discovery is unavailable")

print(json.dumps({"python": "3.12", "python3": "3.12", "unittest": "passed"}, sort_keys=True))
