#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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
    connection.execute("CREATE TABLE receipts (id TEXT PRIMARY KEY, digest TEXT)")
    digest = hashlib.sha256(json.dumps({"status": "local_staged"}, sort_keys=True).encode()).hexdigest()
    connection.execute("INSERT INTO receipts VALUES ('probe', ?)", (digest,))
    if connection.execute("SELECT digest FROM receipts WHERE id='probe'").fetchone() != (digest,):
        raise SystemExit("grader SQLite/hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    substantive_prose,
)):
    raise SystemExit("grader API import probe failed")

print(json.dumps({"python3": "3.10", "sqlite": sqlite3.sqlite_version, "yaml": "passed", "grader_api": "passed"}, sort_keys=True))
