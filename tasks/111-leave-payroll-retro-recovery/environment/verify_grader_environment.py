#!/usr/bin/env python3
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import re
import sqlite3
import sys

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

start = datetime.fromisoformat("2026-08-10T22:30:00-04:00")
end = datetime.fromisoformat("2026-08-11T02:30:00-04:00")
if (end - start).total_seconds() != 14400 or date.fromisoformat("2026-08-10").day != 10:
    raise SystemExit("grader payroll datetime probe failed")
connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE adjustments(id TEXT PRIMARY KEY, hours REAL)")
    connection.execute("INSERT INTO adjustments VALUES(?, ?)", ("RA-1", -4.0))
    row = connection.execute("SELECT id, hours FROM adjustments").fetchone()
finally:
    connection.close()
if row != ("RA-1", -4.0) or len(hashlib.sha256(b"frozen-payroll").hexdigest()) != 64:
    raise SystemExit("grader SQLite/hash probe failed")
if re.fullmatch(r"[A-Z]+-[0-9]+", "APR-9001") is None:
    raise SystemExit("grader record-reference probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases,
        bounded_text_semantic_input,
        explicit_external_action_claims,
        observation,
        sources_unchanged,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {"python3": "3.10", "datetime_offset": "passed", "sqlite": sqlite3.sqlite_version},
        sort_keys=True,
    )
)
