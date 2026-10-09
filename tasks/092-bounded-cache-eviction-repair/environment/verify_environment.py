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
        "task 092 requires CPython 3.12 in the shared agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

state = {"entries": {"pinned": {"value": {"generation": 1}, "size": 4}}}
planned = deepcopy(state)
planned["entries"].pop("pinned")
if "pinned" not in state["entries"]:
    fail("transactional deepcopy probe failed")
if not math.isfinite(json.loads("2.5")) or math.isfinite(float("inf")):
    fail("finite JSON value probe failed")

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

print(json.dumps({"python": "3.12", "python3": "3.12", "transactional_copy": "passed", "finite_json": "passed"}, sort_keys=True))
