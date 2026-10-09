#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import yaml

from harnessbench.grading.pure_function import (
    audit_pure_function,
    expected_results,
    run_pure_function,
)
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    sources_unchanged,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """
def redact_event(event, policy):
    return {"event": dict(event), "redactions": []}
"""
safe, detail = audit_pure_function(source, "redact_event")
if not safe:
    raise SystemExit(f"pure-function audit probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(
    callable(value)
    for value in (
        expected_results,
        run_pure_function,
        explicit_external_action_claims,
        sources_unchanged,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "yaml": "passed",
            "pure_function": "passed",
            "grader_api": "passed",
        },
        sort_keys=True,
    )
)
