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
    observation,
    sources_unchanged,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """
def plan_rpc_budget(calls, policy):
    return {
        'decisions': [{'call_id': row['call_id'], 'action': 'stop'} for row in calls],
        'summary': {'total': len(calls)},
    }
"""
cases = [{"calls": [{"call_id": "rpc-1"}], "policy": {}}]
safe, detail = audit_pure_function(source, "plan_rpc_budget")
if not safe:
    raise SystemExit(f"grader pure audit probe failed: {detail}")
actual, detail = run_pure_function(source, "plan_rpc_budget", cases, ("calls", "policy"))
expected = expected_results(
    lambda calls, policy: {
        "decisions": [{"call_id": row["call_id"], "action": "stop"} for row in calls],
        "summary": {"total": len(calls)},
    },
    cases,
    ("calls", "policy"),
)
if actual != expected:
    raise SystemExit(f"grader pure worker probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader RPC API import probe failed")
print(json.dumps({"python3": "3.10", "pure_worker": "passed", "yaml": "passed"}, sort_keys=True))
