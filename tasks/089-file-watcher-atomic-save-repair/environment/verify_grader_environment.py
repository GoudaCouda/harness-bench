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
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """
def reconcile_batch(checkpoint, batch, policy):
    watched = checkpoint.get("watched", {}).copy()
    paths = sorted(set(item.get("path") for item in batch.get("events", []) if item.get("path")))
    return {"actions": [{"path": path} for path in paths], "checkpoint": {"watched": watched}}
"""
safe, detail = audit_pure_function(
    source,
    "reconcile_batch",
    allowed_methods=("copy", "get"),
)
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
        observation,
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
