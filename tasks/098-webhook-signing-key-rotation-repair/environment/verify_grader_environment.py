#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import yaml

from harnessbench.grading.pure_function import audit_pure_function, expected_results, run_pure_function
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """
import hashlib
import hmac

def verify_batch(deliveries, keyring, policy, checkpoint):
    digest = hmac.new(keyring[0]["secret"].encode(), deliveries[0]["body"].encode(), hashlib.sha256).hexdigest()
    return {"ok": hmac.compare_digest(digest, digest)}
"""
safe, detail = audit_pure_function(
    source,
    "verify_batch",
    allowed_imports=("hashlib", "hmac"),
    allowed_methods=("compare_digest", "encode", "hexdigest", "new"),
)
if not safe:
    raise SystemExit(f"pure-function crypto audit probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(callable(value) for value in (
    expected_results,
    run_pure_function,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)):
    raise SystemExit("grader API import probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "pure_function_crypto": "passed"}, sort_keys=True))
