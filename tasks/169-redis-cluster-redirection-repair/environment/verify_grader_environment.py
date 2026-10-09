#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import yaml
from harnessbench.grading.pure_function import audit_pure_function, run_pure_function
from harnessbench.grading.task_checks import observation, sources_unchanged, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """
def plan_cluster_retries(requests, slots, policy):
    return {
        'decisions': [{'request_id': row['request_id'], 'action': 'complete'} for row in requests],
        'slots': slots,
    }
"""
cases = [{
    "requests": [{"request_id": "r-1"}],
    "slots": [{"slot": 1, "node": "node-a"}],
    "policy": {},
}]
safe, detail = audit_pure_function(source, "plan_cluster_retries")
if not safe:
    raise SystemExit(f"grader pure audit probe failed: {detail}")
actual, detail = run_pure_function(
    source, "plan_cluster_retries", cases, ("requests", "slots", "policy")
)
if not actual or actual[0].get("value", {}).get("decisions") != [
    {"request_id": "r-1", "action": "complete"}
]:
    raise SystemExit(f"grader pure worker probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader Redis task-check API import probe failed")
print(json.dumps({"python3": "3.10", "pure_worker": "passed", "yaml": "passed"}, sort_keys=True))
