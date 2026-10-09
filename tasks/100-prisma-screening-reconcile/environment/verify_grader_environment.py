#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import yaml

from harnessbench.grading.structured_io import (
    contains_control_or_format,
    portable_identifier,
    read_json_file,
    read_strict_csv,
    spreadsheet_formula_text,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

if not portable_identifier("REPORT:001") or portable_identifier("-unsafe"):
    raise SystemExit("portable identifier probe failed")
if not contains_control_or_format("bad\u200btext"):
    raise SystemExit("Unicode safety probe failed")
if not spreadsheet_formula_text(" =HYPERLINK(\"x\")"):
    raise SystemExit("spreadsheet-formula probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(callable(value) for value in (read_json_file, read_strict_csv)):
    raise SystemExit("grader structured-I/O API import probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "structured_io": "passed"}, sort_keys=True))
