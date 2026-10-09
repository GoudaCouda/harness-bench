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
    bounded_text_semantic_input,
    observation,
    read_json_object,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-crm-grader-probe-") as temporary:
    database = Path(temporary) / "crm.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE accounts(id TEXT, status TEXT)")
        connection.executemany(
            "INSERT INTO accounts VALUES (?, ?)",
            [("A-101", "merged_into:A-100"), ("A-100", "active")],
        )
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT id,status FROM accounts ORDER BY id").fetchall()
logical = json.dumps({"accounts": rows}, sort_keys=True).encode()
if len(hashlib.sha256(logical).hexdigest()) != 64:
    raise SystemExit("grader CRM logical-state digest probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input,
    observation,
    read_json_object,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)):
    raise SystemExit("grader CRM oracle API import probe failed")
print(json.dumps({"python3": "3.10", "sqlite": "passed", "logical_digest": "passed", "yaml": "passed"}, sort_keys=True))
