#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
if abs(Decimal("-0.75")) + Decimal("0.25") != Decimal("1.00"):
    raise SystemExit("grader Decimal guard-band probe failed")
with tempfile.TemporaryDirectory(prefix="hb-metrology-grader-probe-") as temporary:
    database = Path(temporary) / "calibration.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE scope(use_id TEXT PRIMARY KEY, review INTEGER)")
        connection.executemany("INSERT INTO scope VALUES (?, ?)", [("old", 0), ("new", 1)])
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        selected = connection.execute("SELECT use_id FROM scope WHERE review=1").fetchall()
    if selected != [("new",)]:
        raise SystemExit("grader SQLite downstream-scope probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("grader calibration database hash probe failed")
if json.loads('{"external_actions_executed":false}')["external_actions_executed"] is not False:
    raise SystemExit("grader external/physical boundary probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader metrology oracle API import probe failed")
print(json.dumps({"python3": "3.10", "decimal": "passed", "sqlite": "passed", "sha256": "passed", "yaml": "passed"}, sort_keys=True))
