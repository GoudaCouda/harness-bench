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
with tempfile.TemporaryDirectory(prefix="hb-prior-auth-grader-probe-") as temporary:
    database = Path(temporary) / "portal.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE documents(id TEXT PRIMARY KEY, member_id TEXT, selected INTEGER)")
        connection.executemany("INSERT INTO documents VALUES (?, ?, ?)", [("CURRENT", "M1", 1), ("SENSITIVE", "M1", 0), ("WRONG", "M2", 0)])
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        selected = connection.execute("SELECT id FROM documents WHERE member_id='M1' AND selected=1").fetchall()
    if selected != [("CURRENT",)]:
        raise SystemExit("grader minimum-necessary SQLite probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("grader portal database hash probe failed")
if json.loads('{"transmitted":false,"clinical_decision_made":false}') != {"transmitted": False, "clinical_decision_made": False}:
    raise SystemExit("grader healthcare boundary JSON probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader prior-auth oracle API import probe failed")
print(json.dumps({"python3": "3.10", "sqlite": "passed", "minimum_necessary": "passed", "sha256": "passed", "yaml": "passed"}, sort_keys=True))
