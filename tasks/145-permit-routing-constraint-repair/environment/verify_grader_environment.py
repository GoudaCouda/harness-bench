#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys

import yaml
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
config = json.loads(
    '{"map_version":"Z-2026.3","precedence":["floodplain","zoning"]}'
)
if config["precedence"] != ["floodplain", "zoning"]:
    raise SystemExit("grader permit JSON probe failed")
if len(hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("grader permit digest probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        bounded_text_semantic_input,
        explicit_external_action_claims,
        observation,
        read_json_object,
        sources_unchanged,
        substantive_prose,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader permit oracle API import probe failed")
print(
    json.dumps(
        {"python3": "3.10", "json": "passed", "sha256": "passed", "yaml": "passed"},
        sort_keys=True,
    )
)
