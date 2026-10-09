#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input, norm, observation, read_csv_rows,
    read_json_object, sources_unchanged, substantive_prose,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
value = {"facts": [{"name": "Revenue", "value": 1250000}]}
payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("grader canonical filing digest probe failed")
with tempfile.TemporaryDirectory(prefix="hb-160-grader-") as directory:
    root = Path(directory)
    (root / "verification.md").write_text("Verified internal filing package only. " * 12)
    semantic = bounded_text_semantic_input(root, "verification.md", min_chars=100)
    if not semantic.get("judge_eligible"):
        raise SystemExit("grader semantic-input probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if norm("No_Live") != "no live":
    raise SystemExit("grader normalization probe failed")
if not all(callable(value) for value in (
    observation, read_csv_rows, read_json_object, sources_unchanged,
    substantive_prose, workspace_redline_violations,
)):
    raise SystemExit("grader filing API import probe failed")
print(json.dumps({"python3": "3.10", "canonical_sha256": "passed", "semantic_input": "passed", "yaml": "passed"}, sort_keys=True))
