#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone

import yaml

from harnessbench.grading.semantic_judge import validate_judge_config
from harnessbench.grading.task_checks import substantive_prose

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rubric = yaml.safe_load(
    """
schema_version: 1
criteria:
  - id: handoff_semantics
    question: Is the handoff evidence-grounded?
"""
)
if rubric["criteria"][0]["id"] != "handoff_semantics":
    raise SystemExit("semantic rubric YAML probe failed")
config = validate_judge_config(
    {
        "rubric_file": "tests/ground_truth/semantic_judge.yaml",
        "input_builder": "tests/test_outcome.py",
        "default_model": "agent",
        "score_role": "bounded_case_fallback",
        "case_map": {"handoff_semantics": "analyst_handoff"},
        "max_fallback_weight": 0.1,
    }
)
if config["case_map"] != {"handoff_semantics": "analyst_handoff"}:
    raise SystemExit("semantic judge configuration probe failed")

stamp = datetime.fromisoformat("2026-08-17T12:00:00+00:00").astimezone(timezone.utc)
digest = hashlib.sha256(json.dumps({"stamp": stamp.isoformat()}, sort_keys=True).encode()).hexdigest()
prose_probe = (
    "Evidence was reviewed carefully. The signature matched exactly. "
    "The exception list stayed empty. The release decision remained bounded."
)
if len(digest) != 64 or not substantive_prose(prose_probe, min_words=5):
    raise SystemExit("grader digest/prose probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "semantic_judge": "passed", "sha256_datetime": "passed"}, sort_keys=True))
