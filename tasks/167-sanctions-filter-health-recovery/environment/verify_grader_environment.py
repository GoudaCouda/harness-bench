#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys

import yaml
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    norm,
    observation,
    read_csv_rows,
    read_json_object,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(csv.DictReader(io.StringIO(
    "item_id,decision,reason_code,owner,next_action,evidence_refs\n"
    "S-401,blocked,exact_match,compliance,review,post_repair_alerts.csv#S-401\n"
)))
if len(rows) != 1 or rows[0]["decision"] != "blocked":
    raise SystemExit("grader sanctions-ledger CSV probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if norm("Pending_Rescreen") != "pending rescreen":
    raise SystemExit("grader normalization probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input, observation, read_csv_rows, read_json_object,
    sources_unchanged, substantive_prose, workspace_redline_violations,
)):
    raise SystemExit("grader sanctions API import probe failed")
print(json.dumps({"python3": "3.10", "csv": "passed", "yaml": "passed"}, sort_keys=True))
