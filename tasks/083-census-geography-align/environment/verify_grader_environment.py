#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
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

rows = list(csv.DictReader(io.StringIO("state,county\n06,001\n")))
if rows != [{"state": "06", "county": "001"}]:
    raise SystemExit("grader CSV leading-zero probe failed")
if json.loads('{"suppressed":null}') != {"suppressed": None}:
    raise SystemExit("grader JSON null probe failed")
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
            "csv_json": "passed",
            "legacy_adapter": "passed",
        },
        sort_keys=True,
    )
)
