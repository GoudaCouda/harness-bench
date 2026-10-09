#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    observation,
    read_json_object,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
raw = b"1\n00:00:01,000 --> 00:00:02,500\nProbe\n"
if len(hashlib.sha256(raw).hexdigest()) != 64:
    raise SystemExit("grader SRT digest probe failed")
with tempfile.TemporaryDirectory(prefix="hb-156-grader-") as directory:
    root = Path(directory)
    (root / "handoff.md").write_text("Verified subtitle timing and offline scope. " * 12)
    payload = bounded_text_semantic_input(root, "handoff.md", min_chars=100)
    if not payload.get("judge_eligible"):
        raise SystemExit("grader semantic-input probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    observation, read_json_object, sources_unchanged,
    substantive_prose, workspace_redline_violations,
)):
    raise SystemExit("grader subtitle API import probe failed")
print(json.dumps({"python3": "3.10", "sha256": "passed", "semantic_input": "passed", "yaml": "passed"}, sort_keys=True))
