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
source = (
    "from urllib.parse import unquote\n"
    "def propagate_contexts(requests, policy):\n"
    "    return unquote(requests[0])\n"
)
safe, detail = audit_pure_function(
    source,
    "propagate_contexts",
    allowed_imports=("urllib.parse",),
)
if not safe:
    raise SystemExit(f"grader trace pure-function audit probe failed: {detail}")
cases = [{"requests": ["alice%20smith"], "policy": {}}]
actual, detail = run_pure_function(
    source,
    "propagate_contexts",
    cases,
    ("requests", "policy"),
    allowed_imports=("urllib.parse",),
)
if not actual or actual[0].get("value") != "alice smith":
    raise SystemExit(f"grader trace restricted subprocess probe failed: {detail}")
expected = expected_results(
    lambda requests, policy: "alice smith",
    cases,
    ("requests", "policy"),
)
if expected != [{"value": "alice smith", "unchanged": True}]:
    raise SystemExit("grader trace expected-result probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)):
    raise SystemExit("grader trace oracle API import probe failed")
print(json.dumps({
    "python3": "3.10",
    "pure_function": "passed",
    "restricted_subprocess": "passed",
    "urllib_parse": "passed",
    "yaml": "passed",
}, sort_keys=True))
