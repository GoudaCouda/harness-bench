#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import re
import sys
import xml.etree.ElementTree as ET

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

row = next(csv.DictReader(io.StringIO("risk_ratio,ci_low\n0.8,0.6\n")))
if not math.isclose(float(row["risk_ratio"]), 0.8):
    raise SystemExit("grader numeric CSV probe failed")
if ET.fromstring("<svg><text>POOLED</text></svg>").find("text") is None:
    raise SystemExit("grader SVG probe failed")
if (
    re.fullmatch(
        r"[A-Za-z0-9_.-]+#[A-Za-z0-9_.:-]+",
        "protocol.json#outcome",
    )
    is None
):
    raise SystemExit("grader evidence-reference probe failed")
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
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "numeric_csv": "passed",
            "svg": "passed",
            "yaml": "passed",
        },
        sort_keys=True,
    )
)
