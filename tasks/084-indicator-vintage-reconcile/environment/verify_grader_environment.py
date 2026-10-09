#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys

import yaml

from harnessbench.grading.legacy_case_adapter import (
    checks_by_id,
    grouped_observations,
    load_private_score,
    source_files_unchanged,
)
from harnessbench.grading.semantic_judge import validate_judge_config
from harnessbench.grading.task_checks import explicit_external_action_claims

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(csv.DictReader(io.StringIO("country,year\nAster,2025\n")))
if rows != [{"country": "Aster", "year": "2025"}]:
    raise SystemExit("grader CSV probe failed")
config = validate_judge_config(
    {
        "rubric_file": "tests/ground_truth/semantic_judge.yaml",
        "input_builder": "tests/test_outcome.py",
        "default_model": "agent",
        "score_role": "bounded_case_fallback",
        "case_map": {
            "indicator_identity": "revision_handoff",
            "source_page_coverage": "revision_handoff",
            "signed_revisions": "revision_handoff",
            "bounded_leader_claim": "revision_handoff",
        },
        "max_fallback_weight": 0.21,
    }
)
if config["max_fallback_weight"] != 0.21:
    raise SystemExit("semantic judge configuration probe failed")
if yaml.safe_load("pages: [1, 2, 3]\n")["pages"] != [1, 2, 3]:
    raise SystemExit("YAML probe failed")
if not all(
    callable(value)
    for value in (
        checks_by_id,
        grouped_observations,
        load_private_score,
        source_files_unchanged,
        explicit_external_action_claims,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "csv_yaml": "passed",
            "legacy_adapter": "passed",
            "semantic_judge": "passed",
        },
        sort_keys=True,
    )
)
