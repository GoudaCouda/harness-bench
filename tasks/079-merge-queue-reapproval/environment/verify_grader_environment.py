#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import inspect
import io
import json
import re
import sys

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(csv.DictReader(io.StringIO("gate,sha\nbuild_linux,bbb222\n")))
if rows != [{"gate": "build_linux", "sha": "bbb222"}]:
    raise SystemExit("CSV parser probe failed")
if re.sub(r"[\\s_:/-]+", " ", "owner_approval") != "owner approval":
    raise SystemExit("normalization regex probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not callable(score_workspace_from_cases) or not callable(inspect.signature) or not callable(importlib.util.spec_from_file_location):
    raise SystemExit("grader API probe failed")

print(json.dumps({"python3": "3.10", "csv_json": "passed", "yaml": "passed", "dynamic_oracle_load": "passed"}, sort_keys=True))
