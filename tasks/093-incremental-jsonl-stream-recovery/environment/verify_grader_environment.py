#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import yaml

from harnessbench.grading.pure_function import audit_pure_function, expected_results, run_pure_function
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """
from copy import deepcopy
import json
import math

def consume_segments(checkpoint, segments, policy):
    values = [json.loads(item.get("data", "null")) for item in segments]
    return {"checkpoint": deepcopy(checkpoint), "values": values, "finite": math.isfinite(policy.get("limit", 0))}
"""
safe, detail = audit_pure_function(
    source,
    "consume_segments",
    allowed_imports=("copy", "json", "math"),
    allowed_methods=("deepcopy", "get", "isfinite", "loads"),
)
if not safe:
    raise SystemExit(f"pure-function audit probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(callable(value) for value in (expected_results, run_pure_function, explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader API import probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "pure_function": "passed", "grader_api": "passed"}, sort_keys=True))
