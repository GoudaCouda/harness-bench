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
        "task 087 requires CPython 3.12 in the shared agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

message = "Bearer abc.DEF then api_key = key-7"
bearer = re.search(r"\bBearer +(?P<secret>[A-Za-z0-9._~+/=\-]+)", message, re.I)
assignment = re.search(r"\bapi_key *= *(?P<secret>[^\s,;]+)", message, re.I)
if bearer is None or bearer.group("secret") != "abc.DEF":
    fail("Bearer-token regular-expression probe failed")
if assignment is None or assignment.group("secret") != "key-7":
    fail("assignment regular-expression probe failed")

probe = subprocess.run(
    [
        "python",
        "-B",
        "-c",
        (
            "import json,pathlib,re,unittest,sys; "
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
            "stdlib": ["json", "pathlib", "re", "unittest"],
            "credential_pattern_probe": "passed",
        },
        sort_keys=True,
    )
)
