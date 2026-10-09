#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(csv.DictReader(io.StringIO("asset_id,sha256\nsurvey,abc\n")))
if rows != [{"asset_id": "survey", "sha256": "abc"}]:
    raise SystemExit("grader CSV probe failed")
if len(hashlib.sha256(b"protected-bytes").hexdigest()) != 64:
    raise SystemExit("grader SHA-256 probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases,
        explicit_external_action_claims,
        observation,
        read_json_object,
        sources_unchanged,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {"python3": "3.10", "csv": "passed", "sha256": "passed", "yaml": "passed"},
        sort_keys=True,
    )
)
