#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from decimal import Decimal

import yaml

from harnessbench.grading.structured_io import (
    read_json_file,
    read_strict_csv,
)
from harnessbench.grading.task_checks import (
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

data = "invoice_line_id,approved_amount,held_amount\nIL-01,97.50,2.50\n"
rows = list(csv.DictReader(io.StringIO(data)))
total = Decimal(rows[0]["approved_amount"]) + Decimal(rows[0]["held_amount"])
if total != Decimal("100.00"):
    raise SystemExit("grader exact-cent reconciliation probe failed")
if len(hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("grader review hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        read_json_file,
        read_strict_csv,
        observation,
        sources_unchanged,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader AP oracle API import probe failed")

print(json.dumps({"python3": "3.10", "csv": "passed", "decimal": "passed", "yaml": "passed"}, sort_keys=True))
