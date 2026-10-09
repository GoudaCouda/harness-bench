#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys

import yaml

from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    substantive_prose,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

probe = {"pairs": [{"client": "a", "server": "b", "result": "pass"}]}
digest = hashlib.sha256(json.dumps(probe, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
    raise SystemExit("canonical digest/regex probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    substantive_prose,
    workspace_redline_violations,
)):
    raise SystemExit("grader task-check API import probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "digest": "passed", "grader_api": "passed"}, sort_keys=True))
