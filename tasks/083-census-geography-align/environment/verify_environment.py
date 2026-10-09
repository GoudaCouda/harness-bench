#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


if sys.version_info[:2] != (3, 12):
    fail(
        "task 083 requires CPython 3.12 in the shared agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

rows = list(
    csv.DictReader(
        io.StringIO(
            "state,county,year,estimate\n"
            "06,001,2024,1000\n"
            "06,007,2025,\n"
        )
    )
)
payload = json.loads('{"missing_markers":[null,"S"]}')
if rows[0]["county"] != "001" or rows[1]["estimate"] != "":
    fail("CSV stable-key/blank-value capability probe failed")
if payload["missing_markers"] != [None, "S"]:
    fail("JSON missing-marker capability probe failed")

probe = subprocess.run(
    [
        sys.executable,
        "-B",
        "-c",
        "import csv,json,pathlib; print('ok')",
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
            "stdlib": ["csv", "json", "pathlib"],
            "stable_key_probe": "passed",
        },
        sort_keys=True,
    )
)
