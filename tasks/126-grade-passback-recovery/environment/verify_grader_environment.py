#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

submitted = datetime.fromisoformat("2026-08-19T23:59:59+00:00")
if submitted.tzinfo != timezone.utc:
    raise SystemExit("grader UTC timestamp probe failed")
connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE gradebook(student TEXT PRIMARY KEY, score INTEGER, manual_override INTEGER)")
    connection.execute("INSERT INTO gradebook VALUES('STU-1', 18, 1)")
    row = connection.execute("SELECT score, manual_override FROM gradebook").fetchone()
finally:
    connection.close()
if row != (18, 1):
    raise SystemExit("grader gradebook SQLite probe failed")
if len(hashlib.sha256(json.dumps(row).encode()).hexdigest()) != 64:
    raise SystemExit("grader semantic-state hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases, bounded_text_semantic_input,
        explicit_external_action_claims, observation,
        read_json_object, sources_unchanged,
        substantive_prose, workspace_redline_violations,
    )
):
    raise SystemExit("grader grade-passback oracle API import probe failed")

print(json.dumps({"python3": "3.10", "utc": "passed", "sqlite": sqlite3.sqlite_version, "sha256": "passed", "yaml": "passed"}, sort_keys=True))
