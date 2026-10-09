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
def select_wheel(target, assets):
    return {"decision": "no_compatible", "filename": None}
"""
safe, detail = audit_pure_function(source, "select_wheel")
if not safe:
    raise SystemExit(f"pure-function audit probe failed: {detail}")
manifest = yaml.safe_load("schema_version: 2\npass_threshold: 0.8\n")
if manifest != {"schema_version": 2, "pass_threshold": 0.8}:
    raise SystemExit("YAML manifest probe failed")
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
