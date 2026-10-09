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
source = (
    "import collections\n"
    "def assess_assertions(credentials, assertions, policy):\n"
    "    rows = collections.deque(credentials)\n"
    "    return {'credentials': list(rows), 'decisions': assertions}\n"
)
safe, detail = audit_pure_function(source, "assess_assertions")
actual, run_detail = run_pure_function(
    source,
    "assess_assertions",
    [{"credentials": [], "assertions": [], "policy": {}}],
    ("credentials", "assertions", "policy"),
)
if not safe or actual != [{"value": {"credentials": [], "decisions": []}, "unchanged": True}]:
    raise SystemExit(f"grader WebAuthn pure-worker probe failed: {detail}; {run_detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (expected_results, observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader WebAuthn oracle API import probe failed")
print(json.dumps({"python3": "3.10", "pure_worker": "passed", "yaml": "passed"}, sort_keys=True))
