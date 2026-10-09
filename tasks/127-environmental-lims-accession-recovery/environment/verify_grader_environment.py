#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    substantive_prose,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

instant = datetime.fromisoformat("2026-08-19T11:15:00+00:00")
if instant.tzinfo != timezone.utc:
    raise SystemExit("grader LIMS UTC timestamp probe failed")
if Decimal("8.1") <= Decimal("6.0"):
    raise SystemExit("grader LIMS temperature-boundary probe failed")
connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE samples(id TEXT PRIMARY KEY, state TEXT, analysis_started INTEGER)")
    connection.execute("INSERT INTO samples VALUES('SMP-26-042', 'quarantine_temperature', 0)")
    row = connection.execute("SELECT state, analysis_started FROM samples").fetchone()
finally:
    connection.close()
if row != ("quarantine_temperature", 0):
    raise SystemExit("grader LIMS SQLite probe failed")
if len(hashlib.sha256(json.dumps(row).encode()).hexdigest()) != 64:
    raise SystemExit("grader LIMS semantic-state hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases, bounded_text_semantic_input,
        explicit_external_action_claims, observation,
        read_json_object, substantive_prose,
    )
):
    raise SystemExit("grader LIMS oracle API import probe failed")

print(json.dumps({"python3": "3.10", "utc": "passed", "decimal": "passed", "sqlite": sqlite3.sqlite_version, "sha256": "passed", "yaml": "passed"}, sort_keys=True))
