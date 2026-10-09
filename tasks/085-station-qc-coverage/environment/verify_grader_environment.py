#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import sys

from harnessbench.grading.legacy_case_adapter import (
    checks_by_id,
    grouped_observations,
    load_private_score,
    source_files_unchanged,
)
from harnessbench.grading.task_checks import explicit_external_action_claims

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(csv.DictReader(io.StringIO("station,value_c\nST-A,13.5\n")))
if rows[0]["station"] != "ST-A" or not math.isclose(float(rows[0]["value_c"]), 13.5):
    raise SystemExit("grader CSV/numeric probe failed")
if not all(
    callable(value)
    for value in (
        checks_by_id,
        grouped_observations,
        load_private_score,
        source_files_unchanged,
        explicit_external_action_claims,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "csv_math": "passed",
            "legacy_adapter": "passed",
        },
        sort_keys=True,
    )
)
