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
def verify_bundles(artifacts, bundles, roots, policy):
    decisions = []
    for artifact in artifacts:
        decisions.append({'artifact': artifact['name'], 'action': 'verify'})
    return {'decisions': decisions}
"""
cases = [{
    "artifacts": [{"name": "app.tar"}],
    "bundles": [],
    "roots": [],
    "policy": {},
}]
safe, detail = audit_pure_function(source, "verify_bundles")
if not safe:
    raise SystemExit(f"grader pure audit probe failed: {detail}")
actual, detail = run_pure_function(
    source, "verify_bundles", cases, ("artifacts", "bundles", "roots", "policy")
)
if not actual or actual[0].get("value") != {
    "decisions": [{"artifact": "app.tar", "action": "verify"}]
}:
    raise SystemExit(f"grader pure worker probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    observation, sources_unchanged, workspace_redline_violations,
)):
    raise SystemExit("grader bundle-policy API import probe failed")
print(json.dumps({"python3": "3.10", "pure_worker": "passed", "yaml": "passed"}, sort_keys=True))
