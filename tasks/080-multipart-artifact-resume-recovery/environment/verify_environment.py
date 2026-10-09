#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


if sys.version_info[:2] != (3, 12):
    fail(
        "task 080 requires CPython 3.12 in the agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

digest = hashlib.sha256(b"multipart-resume-probe").hexdigest()
if not re.fullmatch(r"[0-9a-f]{64}", digest):
    fail("SHA-256/regular-expression capability probe failed")

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
            "sha256": "passed",
            "stdlib": ["hashlib", "json", "re", "unittest"],
        },
        sort_keys=True,
    )
)
