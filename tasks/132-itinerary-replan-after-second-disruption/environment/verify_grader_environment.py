#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
if datetime.fromisoformat("2026-10-17T08:45:00-04:00").utcoffset().total_seconds() != -14400:
    raise SystemExit("grader timezone parser probe failed")
with tempfile.TemporaryDirectory(prefix="hb-itinerary-grader-probe-") as temporary:
    database = Path(temporary) / "travel.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE objects(id TEXT PRIMARY KEY, action TEXT)")
        connection.execute("INSERT INTO objects VALUES ('HOTEL', 'preserve')")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        if connection.execute("SELECT action FROM objects WHERE id='HOTEL'").fetchone()[0] != "preserve":
            raise SystemExit("grader SQLite projection probe failed")
if len(hashlib.sha256(json.dumps({"option": "O-F"}, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("grader itinerary hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader itinerary oracle API import probe failed")
print(json.dumps({"python3": "3.10", "timezone": "passed", "sqlite": "passed", "sha256": "passed", "yaml": "passed"}, sort_keys=True))
