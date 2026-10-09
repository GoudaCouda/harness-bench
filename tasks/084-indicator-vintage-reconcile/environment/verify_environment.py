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
        "task 084 requires CPython 3.12 in the shared agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

pages = [
    json.loads('{"page":1,"pages":3,"rows":[{"country":"Aster","year":2025}]}'),
    json.loads('{"page":2,"pages":3,"rows":[{"country":"Boron","year":2025}]}'),
    json.loads('{"page":3,"pages":3,"rows":[{"country":"Cygnus","year":2025}]}'),
]
prior = list(
    csv.DictReader(
        io.StringIO(
            "country,year,indicator,value\n"
            "Aster,2024,GDPCON15,505\n"
        )
    )
)
if [page["page"] for page in pages] != [1, 2, 3]:
    fail("JSON pagination capability probe failed")
if prior[0]["indicator"] != "GDPCON15":
    fail("CSV vintage capability probe failed")

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
            "pagination_probe": "passed",
        },
        sort_keys=True,
    )
)
