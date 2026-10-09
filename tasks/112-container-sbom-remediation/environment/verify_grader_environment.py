#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import itertools
import json
import sys

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

versions = ("4.8.0", "4.9.0")
loaders = ("2.2.0", "2.3.0")
if list(itertools.product(versions, loaders))[-1] != ("4.9.0", "2.3.0"):
    raise SystemExit("grader dependency-product probe failed")
payload = json.dumps({"subject": "sha256:probe"}, sort_keys=True).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("grader content-addressing probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases,
        bounded_text_semantic_input,
        explicit_external_action_claims,
        observation,
        read_json_object,
        sources_unchanged,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "dependency_graph": "passed",
            "sha256": "passed",
            "yaml": "passed",
        },
        sort_keys=True,
    )
)
