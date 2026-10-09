#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import sys

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

data = "event_id,sequence\nEV-30,30\nEV-10,10\n"
rows = list(csv.DictReader(io.StringIO(data)))
rows.sort(key=lambda row: int(row["sequence"]))
if [row["event_id"] for row in rows] != ["EV-10", "EV-30"]:
    raise SystemExit("grader ordered-evidence CSV probe failed")
connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE audit(seq INTEGER PRIMARY KEY, contract_id TEXT)")
    connection.executemany("INSERT INTO audit VALUES(?, ?)", [(1, "C-401"), (2, "C-402")])
    count = connection.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
finally:
    connection.close()
if count != 2:
    raise SystemExit("grader closeout audit SQLite probe failed")
if len(hashlib.sha256(json.dumps(rows).encode()).hexdigest()) != 64:
    raise SystemExit("grader semantic-plan hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases, bounded_text_semantic_input, explicit_external_action_claims,
        observation, sources_unchanged,
        substantive_prose, workspace_redline_violations,
    )
):
    raise SystemExit("grader closeout oracle API import probe failed")

print(json.dumps({"python3": "3.10", "csv_order": "passed", "sqlite": sqlite3.sqlite_version, "sha256": "passed", "yaml": "passed"}, sort_keys=True))
