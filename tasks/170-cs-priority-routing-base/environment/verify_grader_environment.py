#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys

import yaml
from harnessbench.grading.task_checks import (
    observation, read_csv_rows, read_json_object, sources_unchanged,
    substantive_prose, workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(csv.DictReader(io.StringIO(
    "item_id,decision,owner\nS-1,p1,incident_response\n"
)))
if rows != [{"item_id": "S-1", "decision": "p1", "owner": "incident_response"}]:
    raise SystemExit("grader CSV probe failed")
raw = json.dumps({"precedence": ["acknowledged", "critical"]}, sort_keys=True).encode()
if len(hashlib.sha256(raw).hexdigest()) != 64:
    raise SystemExit("grader SHA-256 probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
apis = (
    observation, read_csv_rows, read_json_object, sources_unchanged,
    substantive_prose, workspace_redline_violations,
)
if not all(callable(value) for value in apis):
    raise SystemExit("grader routing API import probe failed")
print(json.dumps({
    "python3": "3.10",
    "csv": "passed",
    "sha256": "passed",
    "yaml": "passed",
}, sort_keys=True))
