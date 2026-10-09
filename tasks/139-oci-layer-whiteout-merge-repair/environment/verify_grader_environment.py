#!/usr/bin/env python3
from __future__ import annotations

import json
import posixpath
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
    "import posixpath\n"
    "def merge_layers(layers, policy):\n"
    "    return posixpath.normpath(layers[0])\n"
)
safe, detail = audit_pure_function(
    source,
    "merge_layers",
    allowed_imports=("posixpath",),
)
if not safe:
    raise SystemExit(f"grader pure-function audit probe failed: {detail}")
cases = [{"layers": ["etc/../usr/bin"], "policy": {}}]
actual, detail = run_pure_function(
    source,
    "merge_layers",
    cases,
    ("layers", "policy"),
    allowed_imports=("posixpath",),
)
if not actual or actual[0].get("value") != "usr/bin":
    raise SystemExit(f"grader restricted subprocess/POSIX-path probe failed: {detail}")
expected = expected_results(
    lambda layers, policy: posixpath.normpath(layers[0]),
    cases,
    ("layers", "policy"),
)
if expected != [{"value": "usr/bin", "unchanged": True}]:
    raise SystemExit("grader expected-result probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)):
    raise SystemExit("grader OCI oracle API import probe failed")
print(json.dumps({
    "python3": "3.10",
    "pure_function": "passed",
    "posixpath": "passed",
    "restricted_subprocess": "passed",
    "yaml": "passed",
}, sort_keys=True))
