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
with tempfile.TemporaryDirectory(prefix="hb-formulary-grader-probe-") as temporary:
    database = Path(temporary) / "formulary.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE rules(id TEXT PRIMARY KEY, effective_at TEXT)")
        connection.executemany(
            "INSERT INTO rules VALUES (?, ?)",
            [("OLD", "2025-01-01"), ("NEW", "2026-01-01")],
        )
        connection.commit()
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "SELECT id FROM rules WHERE effective_at<=? ORDER BY effective_at DESC LIMIT 1",
            ("2025-06-01",),
        ).fetchone()
    if row != ("OLD",) or len(digest) != 64:
        raise SystemExit("grader temporal formulary SQLite/hash probe failed")
if json.loads('{"external_actions_executed":false}') != {"external_actions_executed": False}:
    raise SystemExit("grader formulary boundary JSON probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)):
    raise SystemExit("grader formulary oracle API import probe failed")
print(json.dumps({
    "python3": "3.10",
    "sqlite": "passed",
    "temporal_query": "passed",
    "sha256": "passed",
    "yaml": "passed",
}, sort_keys=True))
