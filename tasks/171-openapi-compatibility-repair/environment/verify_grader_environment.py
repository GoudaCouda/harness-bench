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
def compare_api_schemas(old_schemas, new_schemas, policy):
    old_names = set(old_schemas)
    new_names = set(new_schemas)
    return {'removed': sorted(old_names - new_names), 'added': sorted(new_names - old_names)}
"""
cases = [{"old_schemas": {"Old": {}}, "new_schemas": {"New": {}}, "policy": {}}]
safe, detail = audit_pure_function(source, "compare_api_schemas")
if not safe:
    raise SystemExit(f"grader pure audit probe failed: {detail}")
actual, detail = run_pure_function(
    source, "compare_api_schemas", cases, ("old_schemas", "new_schemas", "policy")
)
if not actual or actual[0].get("value") != {"removed": ["Old"], "added": ["New"]}:
    raise SystemExit(f"grader pure worker probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader compatibility API import probe failed")
print(json.dumps({"python3": "3.10", "pure_worker": "passed", "yaml": "passed"}, sort_keys=True))
