#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
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

if re.fullmatch(r"[0-9a-f]{64}", hashlib.sha256(b"snapshot").hexdigest()) is None:
    raise SystemExit("grader snapshot-checksum probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        audit_pure_function,
        expected_results,
        run_pure_function,
        explicit_external_action_claims,
        observation,
        sources_unchanged,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "snapshot_checksum": "passed",
            "yaml": "passed",
        },
        sort_keys=True,
    )
)
