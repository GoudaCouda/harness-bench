#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-royalty-grader-probe-") as temporary:
    database = Path(temporary) / "ledger.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE signed_totals(units INTEGER, cents INTEGER)")
        connection.executemany("INSERT INTO signed_totals VALUES (?, ?)", [(1530, 185000), (950, 95000)])
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        totals = connection.execute("SELECT SUM(units), SUM(cents) FROM signed_totals").fetchone()
    if totals != (2480, 280000):
        raise SystemExit("grader SQLite signed-conservation probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("grader royalty-ledger hash probe failed")
if json.loads('{"external_actions_executed":false}')["external_actions_executed"] is not False:
    raise SystemExit("grader JSON boundary probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations,
)):
    raise SystemExit("grader royalty oracle API import probe failed")
print(json.dumps({"python3": "3.10", "sqlite": "passed", "signed_conservation": "passed", "sha256": "passed", "yaml": "passed"}, sort_keys=True))
