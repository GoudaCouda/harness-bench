#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import datetime

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

stamp = datetime.fromisoformat("2026-05-04T01:13:00+00:00")
if stamp.utcoffset() is None or stamp.isoformat() != "2026-05-04T01:13:00+00:00":
    raise SystemExit("timezone-aware event parsing probe failed")

rows = list(
    csv.DictReader(
        io.StringIO(
            "update_id,component,timestamp,classification,status,reason\n"
            "UP-003,inventory-db,2026-05-04T01:13:00Z,seen,degraded,first occurrence\n"
        )
    )
)
if rows[0]["update_id"] != "UP-003" or not re.search(r"inventory[-_]db", rows[0]["component"]):
    raise SystemExit("event-ledger CSV/regex probe failed")

manifest = yaml.safe_load(
    """
schema_version: 2
task_id: probe
pass_threshold: 0.8
cases:
  - id: observation_a
    weight: 0.4
    title: Observation A
    description: First environment aggregation probe
    core: true
  - id: observation_b
    weight: 0.4
    core: true
    title: Observation B
    description: Second environment aggregation probe
  - id: observation_c
    weight: 0.2
    core: false
    title: Observation C
    description: Third environment aggregation probe
"""
)
result = score_workspace_from_cases(
    ".",
    manifest=manifest,
    evaluate_cases=lambda _: {name: {"pass": True} for name in ("observation_a", "observation_b", "observation_c")},
    task_id="probe",
)
if result["outcome_score"] != 1.0:
    raise SystemExit("outcome-case aggregation probe failed")

print(json.dumps({"python3": "3.10", "event_time": "passed", "csv_regex": "passed", "outcome_cases": "passed"}, sort_keys=True))
