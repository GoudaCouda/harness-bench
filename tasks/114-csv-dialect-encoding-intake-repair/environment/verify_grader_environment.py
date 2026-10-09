#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys

import yaml

from harnessbench.grading.pure_function import (
    audit_pure_function,
    expected_results,
    run_pure_function,
)
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(csv.reader(io.StringIO('name,note\r\nAda,"a,b"\r\n')))
if rows != [["name", "note"], ["Ada", "a,b"]]:
    raise SystemExit("grader quoted CSV probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        audit_pure_function,
        expected_results,
        run_pure_function,
        bounded_text_semantic_input,
        explicit_external_action_claims,
        observation,
        sources_unchanged,
        substantive_prose,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {"python3": "3.10", "csv_quoted_fields": "passed", "yaml": "passed"},
        sort_keys=True,
    )
)
