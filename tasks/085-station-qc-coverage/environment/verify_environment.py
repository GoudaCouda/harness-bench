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
        "task 085 requires CPython 3.12 in the shared agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

rows = list(
    csv.DictReader(
        io.StringIO(
            "station,value,unit\n"
            "ST-A,120,tenths_C\n"
            "ST-C,50,F\n"
        )
    )
)
converted = [
    float(rows[0]["value"]) / 10,
    (float(rows[1]["value"]) - 32) * 5 / 9,
]
if not math.isclose(converted[0], 12.0) or not math.isclose(converted[1], 10.0):
    fail("CSV/unit-conversion capability probe failed")

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
            "unit_conversion_probe": "passed",
        },
        sort_keys=True,
    )
)
