#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    norm,
    observation,
    read_csv_rows,
    read_json_object,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-155-grader-") as directory:
    root = Path(directory)
    (root / "audit.md").write_text("Verified local screening evidence only. " * 15)
    payload = bounded_text_semantic_input(root, "audit.md", min_chars=100)
    if not payload.get("judge_eligible") or payload.get("artifact") != "audit.md":
        raise SystemExit("grader semantic-input probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if norm("Pending_System") != "pending system":
    raise SystemExit("grader normalization probe failed")
if not all(callable(value) for value in (
    observation,
    read_csv_rows,
    read_json_object,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)):
    raise SystemExit("grader screening API import probe failed")
print(json.dumps({"python3": "3.10", "semantic_input": "passed", "yaml": "passed"}, sort_keys=True))
