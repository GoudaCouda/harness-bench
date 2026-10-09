#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


if sys.version_info[:2] != (3, 12):
    fail(
        "task 076 requires CPython 3.12 in the agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

choices = [("5.4.2", "5.4.3"), ("3.2.1",)]
expected = [("5.4.2", "3.2.1"), ("5.4.3", "3.2.1")]
if list(itertools.product(*choices)) != expected:
    fail("itertools.product capability probe returned an unexpected result")

probe = subprocess.run(
    [
        sys.executable,
        "-B",
        "-c",
        "import itertools,json,pathlib; print('ok')",
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
            "python": "3.12",
            "stdlib": ["itertools", "json", "pathlib"],
            "cartesian_product": "passed",
        },
        sort_keys=True,
    )
)
