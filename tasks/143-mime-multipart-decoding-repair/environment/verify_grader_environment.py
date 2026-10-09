#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import yaml
from harnessbench.grading.pure_function import (
    audit_pure_function,
    run_pure_function,
)
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
source = (
    "import quopri\n"
    "def decode(requests, policy):\n"
    "    return quopri.decodestring(requests[0]).decode()\n"
)
safe, detail = audit_pure_function(
    source,
    "decode",
    allowed_imports=("quopri",),
)
if not safe:
    raise SystemExit(f"grader MIME pure-function audit probe failed: {detail}")
actual, detail = run_pure_function(
    source,
    "decode",
    [{"requests": ["hello=20world"], "policy": {}}],
    ("requests", "policy"),
    allowed_imports=("quopri",),
)
if not actual or actual[0].get("value") != "hello world":
    raise SystemExit(f"grader MIME restricted subprocess probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)):
    raise SystemExit("grader MIME oracle API import probe failed")
print(json.dumps({
    "python3": "3.10",
    "pure_function": "passed",
    "quopri": "passed",
    "restricted_subprocess": "passed",
    "yaml": "passed",
}, sort_keys=True))
