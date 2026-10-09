#!/usr/bin/env python3
from __future__ import annotations
import json
import sqlite3
import sys
import yaml
from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import observation, sources_unchanged, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
with sqlite3.connect(":memory:") as connection:
    connection.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO probe(value) VALUES ('ok')")
    if connection.execute("SELECT value FROM probe").fetchone() != ("ok",):
        raise SystemExit("grader SQLite probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (score_workspace_from_cases, observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader API import probe failed")
print(json.dumps({"harnessbench_grader": "passed", "python3": "3.10", "sqlite": sqlite3.sqlite_version, "yaml": "passed"}, sort_keys=True))
