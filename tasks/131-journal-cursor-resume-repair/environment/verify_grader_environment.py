#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import observation, sources_unchanged, substantive_prose, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-journal-grader-probe-") as temporary:
    database = Path(temporary) / "projection.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE cursor(segment TEXT, line_no INTEGER, event_id TEXT)")
        connection.execute("INSERT INTO cursor VALUES ('segment-2', 6, 'e108')")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        cursor = connection.execute("SELECT segment, line_no, event_id FROM cursor").fetchone()
    if cursor != ("segment-2", 6, "e108"):
        raise SystemExit("grader SQLite cursor probe failed")
completed = subprocess.run(["python3", "-c", "print('replay')"], text=True, capture_output=True, timeout=5)
if completed.returncode != 0 or completed.stdout.strip() != "replay":
    raise SystemExit("grader writable-copy replay subprocess probe failed")
if json.loads('{"newly_applied_event_ids":[]}')["newly_applied_event_ids"] != []:
    raise SystemExit("grader replay receipt JSON probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (observation, sources_unchanged, substantive_prose, workspace_redline_violations)):
    raise SystemExit("grader journal oracle API import probe failed")
print(json.dumps({"python3": "3.10", "sqlite": "passed", "subprocess": "passed", "json": "passed", "yaml": "passed"}, sort_keys=True))
