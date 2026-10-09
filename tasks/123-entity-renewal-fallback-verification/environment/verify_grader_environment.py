#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import date

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

if date.fromisoformat("2026-08-19").isoformat() != "2026-08-19":
    raise SystemExit("grader effective-date probe failed")
connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE vendors(id TEXT PRIMARY KEY, revision INTEGER)")
    connection.executemany("INSERT INTO vendors VALUES(?, ?)", [("VND-ALP-17", 41), ("VND-CYP-31", 41)])
    rows = connection.execute("SELECT id, revision FROM vendors ORDER BY id").fetchall()
finally:
    connection.close()
if rows != [("VND-ALP-17", 41), ("VND-CYP-31", 41)]:
    raise SystemExit("grader vendor-master SQLite probe failed")
if len(hashlib.sha256(json.dumps(rows).encode()).hexdigest()) != 64:
    raise SystemExit("grader semantic-state hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases, bounded_text_semantic_input,
        explicit_external_action_claims, observation, read_json_object,
        sources_unchanged, substantive_prose, workspace_redline_violations,
    )
):
    raise SystemExit("grader vendor-renewal oracle API import probe failed")

print(json.dumps({"python3": "3.10", "date": "passed", "sqlite": sqlite3.sqlite_version, "sha256": "passed", "yaml": "passed"}, sort_keys=True))
