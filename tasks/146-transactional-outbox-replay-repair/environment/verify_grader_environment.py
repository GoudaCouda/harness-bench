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
    "import collections\n"
    "def recover_outbox(events, receipts, policy):\n"
    "    rows = collections.deque(events)\n"
    "    return {'state': list(rows), 'actions': []}\n"
)
safe, detail = audit_pure_function(source, "recover_outbox")
actual, run_detail = run_pure_function(
    source,
    "recover_outbox",
    [{"events": [], "receipts": [], "policy": {}}],
    ("events", "receipts", "policy"),
)
if not safe or actual != [{"value": {"state": [], "actions": []}, "unchanged": True}]:
    raise SystemExit(f"grader outbox pure-worker probe failed: {detail}; {run_detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    expected_results,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)):
    raise SystemExit("grader outbox oracle API import probe failed")
print(json.dumps({"python3": "3.10", "pure_worker": "passed", "yaml": "passed"}, sort_keys=True))
