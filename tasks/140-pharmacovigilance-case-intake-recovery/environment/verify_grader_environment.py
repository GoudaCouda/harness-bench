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
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-pv-grader-probe-") as temporary:
    database = Path(temporary) / "pv.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE submissions(id TEXT PRIMARY KEY, status TEXT)")
        connection.executemany(
            "INSERT INTO submissions VALUES (?, ?)",
            [("S1", "accepted"), ("S2", "pending")],
        )
        connection.commit()
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT id,status FROM submissions ORDER BY id").fetchall()
    if rows != [("S1", "accepted"), ("S2", "pending")] or len(digest) != 64:
        raise SystemExit("grader pharmacovigilance SQLite/hash probe failed")
if json.loads('{"external_transmissions_executed":false}') != {"external_transmissions_executed": False}:
    raise SystemExit("grader external-boundary JSON probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)):
    raise SystemExit("grader pharmacovigilance oracle API import probe failed")
print(json.dumps({
    "python3": "3.10",
    "sqlite": "passed",
    "sha256": "passed",
    "json": "passed",
    "yaml": "passed",
}, sort_keys=True))
