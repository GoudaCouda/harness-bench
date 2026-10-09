#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys

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

connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE events(uid TEXT, recurrence_id TEXT, sequence INTEGER, PRIMARY KEY(uid, recurrence_id))")
    connection.execute("INSERT INTO events VALUES(?, ?, ?)", ("ops@example.test", "master", 2))
    row = connection.execute("SELECT uid, recurrence_id, sequence FROM events").fetchone()
finally:
    connection.close()
if row != ("ops@example.test", "master", 2):
    raise SystemExit("grader calendar SQLite probe failed")
if len(hashlib.sha256(json.dumps({"uid": "ops@example.test", "sequence": 2}, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("grader semantic-state hash probe failed")
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
        substantive_prose,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {"python3": "3.10", "sqlite_calendar": "passed", "sha256": "passed", "yaml": "passed"},
        sort_keys=True,
    )
)
