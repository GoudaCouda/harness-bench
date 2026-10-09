#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import json
import math
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


if sys.version_info[:2] != (3, 12):
    fail(
        "task 093 requires CPython 3.12 in the shared agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

record = json.loads('{"id":3,"payload":{"ok":true}}\r')
copied = deepcopy(record)
copied["payload"]["ok"] = False
if record != {"id": 3, "payload": {"ok": True}}:
    fail("JSON parsing/deepcopy isolation probe failed")
if not math.isfinite(json.loads("1.0")) or math.isfinite(float("nan")):
    fail("finite JSON payload probe failed")

probe = subprocess.run(
    ["python", "-B", "-c", "import copy,json,math,pathlib,unittest,sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0:
    fail(f"python alias/stdlib probe failed: {probe.stderr.strip()}")
if probe.stdout.strip() != "3.12":
    fail(f"python alias is not CPython 3.12: {probe.stdout.strip()!r}")

print(json.dumps({"python": "3.12", "python3": "3.12", "jsonl": "passed", "deepcopy": "passed"}, sort_keys=True))
