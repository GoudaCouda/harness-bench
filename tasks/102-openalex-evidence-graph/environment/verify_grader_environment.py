#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys

import yaml

from harnessbench.grading.structured_io import StructuredDataError, read_json_file
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    norm,
    observation,
    read_csv_rows,
    read_json_object,
    sources_unchanged,
    substantive_prose,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

if norm("Review_required") != "review required":
    raise SystemExit("normalization probe failed")
digest = hashlib.sha256(json.dumps({"page": 4}, sort_keys=True).encode()).hexdigest()
if re.fullmatch(r"[0-9a-f]{64}", digest) is None or not callable(csv.DictReader):
    raise SystemExit("CSV/hash/regex probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(callable(value) for value in (
    read_json_file,
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_csv_rows,
    read_json_object,
    sources_unchanged,
    substantive_prose,
)):
    raise SystemExit("grader API import probe failed")
if not issubclass(StructuredDataError, Exception):
    raise SystemExit("structured-data error contract unavailable")

print(json.dumps({"python3": "3.10", "yaml": "passed", "structured_io": "passed", "grader_api": "passed"}, sort_keys=True))
