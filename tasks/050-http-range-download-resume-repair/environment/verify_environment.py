#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
python = shutil.which("python")
if not python:
    raise SystemExit("task command requires the python alias")
version = subprocess.run(
    [python, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if version.returncode != 0 or version.stdout.strip() != "3.12":
    raise SystemExit(f"python alias probe failed: {version.stdout!r} {version.stderr!r}")

match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", "bytes 4-7/8")
if not match or tuple(map(int, match.groups())) != (4, 7, 8):
    raise SystemExit("Content-Range parsing probe failed")
result = {"action": "complete", "reason": "range_complete", "offset": 8}
if json.loads(json.dumps(result, sort_keys=True)) != result:
    raise SystemExit("resume result JSON probe failed")

print(json.dumps({"python": "3.12", "content_range": "passed", "json": "passed"}, sort_keys=True))
