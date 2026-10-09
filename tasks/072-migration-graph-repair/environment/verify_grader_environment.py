#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import yaml

from harnessbench.grading.deterministic_oracle import score_workspace_from_spec
from harnessbench.grading.outcome_cases import score_workspace_from_cases

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

manifest = yaml.safe_load(
    """
schema_version: 2
task_id: environment-probe
pass_threshold: 0.8
cases:
  - id: graph
    title: Graph simulation
    description: Trusted simulation verifies the repaired migration graph.
    weight: 0.8
    core: true
  - id: handoff
    title: Maintainer handoff
    description: The change log records replay and reverse evidence.
    weight: 0.2
    core: false
"""
)
if sum(float(case["weight"]) for case in manifest["cases"]) != 1.0:
    raise SystemExit("case manifest YAML probe failed")
if not callable(score_workspace_from_spec) or not callable(score_workspace_from_cases):
    raise SystemExit("grader API import probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "grader_apis": "passed"}, sort_keys=True))
