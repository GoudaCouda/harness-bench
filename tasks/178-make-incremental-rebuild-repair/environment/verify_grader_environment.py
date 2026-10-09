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
def plan_make_incremental_rebuild(nodes, policy):
    return {'order': [row['id'] for row in nodes], 'rebuild': [], 'up_to_date': [], 'missing': [], 'cycles': []}
"""
cases = [{"nodes":[{"id":"app"}],"policy":{"targets":["app"]}}]
safe, detail = audit_pure_function(source, "plan_make_incremental_rebuild")
if not safe:
    raise SystemExit(detail)
actual, detail = run_pure_function(source, "plan_make_incremental_rebuild", cases, ("nodes","policy"))
if not actual or actual[0].get("value") != {
    "order":["app"],"rebuild":[],"up_to_date":[],"missing":[],"cycles":[]
}:
    raise SystemExit(detail)
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    observation, sources_unchanged, workspace_redline_violations
)):
    raise SystemExit("grader build-plan API import probe failed")
print(json.dumps({"python3":"3.10","pure_worker":"passed","yaml":"passed"},sort_keys=True))
