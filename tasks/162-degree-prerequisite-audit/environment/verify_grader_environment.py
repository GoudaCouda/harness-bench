#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys

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

with sqlite3.connect(":memory:") as connection:
    connection.execute("CREATE TABLE prerequisite(course TEXT, prerequisite TEXT)")
    connection.execute("INSERT INTO prerequisite VALUES ('CS-301', 'CS-201')")
    value = connection.execute(
        "SELECT prerequisite FROM prerequisite WHERE course = ?", ("CS-301",)
    ).fetchone()
if value != ("CS-201",):
    raise SystemExit("grader SQLite probe failed")

plan = {"student_id": "S-42", "requirements": [{"id": "core", "status": "met"}]}
payload = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("grader receipt-digest probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input, observation, read_json_object, sources_unchanged,
    substantive_prose, workspace_redline_violations,
)):
    raise SystemExit("grader degree-audit API import probe failed")
print(json.dumps({"python3": "3.10", "sqlite": sqlite3.sqlite_version,
                  "canonical_sha256": "passed", "yaml": "passed"}, sort_keys=True))
