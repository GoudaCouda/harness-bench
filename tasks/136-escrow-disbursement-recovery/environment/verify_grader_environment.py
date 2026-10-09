#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-escrow-grader-probe-") as temporary:
    database = Path(temporary) / "escrow.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE instructions(id TEXT PRIMARY KEY, amount INTEGER, holdback INTEGER)")
        connection.executemany("INSERT INTO instructions VALUES (?, ?, ?)", [("I1", 7200000, 0), ("I2", 2720000, 80000)])
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        total = connection.execute("SELECT SUM(amount)+SUM(holdback) FROM instructions").fetchone()[0]
    if total != 10000000:
        raise SystemExit("grader SQLite escrow conservation probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("grader escrow database hash probe failed")
if json.loads('{"external_actions_executed":false}')["external_actions_executed"] is not False:
    raise SystemExit("grader external action boundary probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader escrow oracle API import probe failed")
print(json.dumps({"python3": "3.10", "sqlite": "passed", "funds_conservation": "passed", "sha256": "passed", "yaml": "passed"}, sort_keys=True))
