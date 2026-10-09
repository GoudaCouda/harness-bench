#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


if sys.version_info[:2] != (3, 12):
    fail(
        "task 082 requires CPython 3.12 in the agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

token = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", "charge-9:v1")
delays = [min(250 * (2 ** (attempt - 1)), 5000) for attempt in range(1, 5)]
if token is None or delays != [250, 500, 1000, 2000]:
    fail("retry token/backoff capability probe failed")

probe = subprocess.run(
    [
        "python",
        "-B",
        "-c",
        (
            "import json,re,unittest,sys; "
            "print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        ),
    ],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0:
    fail(f"python alias/stdlib probe failed: {probe.stderr.strip()}")
if probe.stdout.strip() != "3.12":
    fail(f"python alias is not CPython 3.12: {probe.stdout.strip()!r}")

print(
    json.dumps(
        {
            "python": "3.12",
            "python3": "3.12",
            "stdlib": ["json", "re", "unittest"],
            "retry_policy_probe": "passed",
        },
        sort_keys=True,
    )
)
