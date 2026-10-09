#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys

import yaml

from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    substantive_prose,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

with sqlite3.connect(":memory:") as connection:
    connection.execute("CREATE TABLE state (id TEXT PRIMARY KEY, value INTEGER)")
    connection.execute("INSERT INTO state VALUES ('probe', 1)")
    if connection.execute("SELECT value FROM state WHERE id='probe'").fetchone() != (1,):
        raise SystemExit("grader SQLite probe failed")

manifest = yaml.safe_load("schema_version: 2\npass_threshold: 0.8\n")
if manifest != {"schema_version": 2, "pass_threshold": 0.8}:
    raise SystemExit("YAML manifest probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    substantive_prose,
)):
    raise SystemExit("grader task-check API import probe failed")

print(json.dumps({"python3": "3.10", "sqlite": sqlite3.sqlite_version, "yaml": "passed", "grader_api": "passed"}, sort_keys=True))
