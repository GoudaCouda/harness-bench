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
        "task 081 requires CPython 3.12 in the agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

wheel = "demo_kit-1.0-py3-none-any.whl"
match = re.fullmatch(
    r"(?P<name>[A-Za-z0-9_]+)-(?P<version>[A-Za-z0-9.]+)-"
    r"(?P<python>[A-Za-z0-9_.]+)-(?P<abi>[A-Za-z0-9_.]+)-"
    r"(?P<platform>[A-Za-z0-9_.]+)\.whl",
    wheel,
)
if match is None or match.group("platform") != "any":
    fail("wheel filename/regular-expression capability probe failed")

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
            "wheel_tag_probe": "passed",
        },
        sort_keys=True,
    )
)
