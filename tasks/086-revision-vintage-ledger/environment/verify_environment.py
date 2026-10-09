#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


if sys.version_info[:2] != (3, 12):
    fail(
        "task 086 requires CPython 3.12 in the shared agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

preliminary = list(
    csv.DictReader(io.StringIO("series,month,value\nEMP_SA,2026-06,108.0\n"))
)
revised = list(
    csv.DictReader(io.StringIO("series,month,value\nEMP_SA,2026-06,102.0\n"))
)
delta = float(revised[0]["value"]) - float(preliminary[0]["value"])
claims = json.loads('[{"id":"employment_increased","series":"EMP_SA"}]')
if not math.isclose(delta, -6.0) or claims[0]["id"] != "employment_increased":
    fail("CSV revision/JSON claim capability probe failed")

probe = subprocess.run(
    [
        sys.executable,
        "-B",
        "-c",
        "import csv,json,math,pathlib; print('ok')",
    ],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    fail(f"stdlib subprocess probe failed: {probe.stderr.strip()}")

print(
    json.dumps(
        {
            "python3": "3.12",
            "stdlib": ["csv", "json", "math", "pathlib"],
            "revision_delta_probe": "passed",
        },
        sort_keys=True,
    )
)
