#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    norm,
    observation,
    read_json_object,
    sources_unchanged,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

connection = sqlite3.connect(":memory:")
try:
    connection.executescript(
        "CREATE TABLE edges(a TEXT, b TEXT);"
        "INSERT INTO edges VALUES('v4', 'v3');"
    )
    row = connection.execute("SELECT a, b FROM edges").fetchone()
finally:
    connection.close()
if row != ("v4", "v3"):
    raise SystemExit("grader SQLite probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases,
        explicit_external_action_claims,
        norm,
        observation,
        read_json_object,
        sources_unchanged,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {"python3": "3.10", "sqlite": sqlite3.sqlite_version, "yaml": "passed"},
        sort_keys=True,
    )
)
