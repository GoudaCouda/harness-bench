#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import sys

import yaml

from harnessbench.grading.legacy_case_adapter import grouped_observations, load_private_score
from harnessbench.grading.task_checks import explicit_external_action_claims

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(csv.DictReader(io.StringIO("path,owner\nsrc/a.py,platform\n")))
if rows != [{"path": "src/a.py", "owner": "platform"}]:
    raise SystemExit("CSV parser probe failed")
manifest = yaml.safe_load("schema_version: 2\npass_threshold: 0.8\n")
if manifest["pass_threshold"] != 0.8:
    raise SystemExit("YAML manifest probe failed")
if re.sub(r"[\s_:/-]+", " ", "old_sha") != "old sha":
    raise SystemExit("normalization regex probe failed")
if not all(callable(value) for value in (grouped_observations, load_private_score, explicit_external_action_claims)):
    raise SystemExit("grader API import probe failed")

print(json.dumps({"python3": "3.10", "csv_json": "passed", "yaml": "passed", "legacy_adapter": "passed"}, sort_keys=True))
