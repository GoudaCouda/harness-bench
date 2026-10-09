#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys

import yaml

from harnessbench.grading.legacy_case_adapter import (
    grouped_observations,
    load_private_score,
    source_files_unchanged,
)
from harnessbench.grading.task_checks import explicit_external_action_claims


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

connection = sqlite3.connect(":memory:")
try:
    connection.executescript(
        """
        CREATE TABLE facts(id TEXT, key TEXT);
        CREATE TABLE dimension(key TEXT, current INTEGER);
        INSERT INTO facts VALUES ('f1', 'a');
        INSERT INTO dimension VALUES ('a', 0), ('a', 1);
        CREATE VIEW joined AS
        WITH usable AS (
          SELECT key FROM dimension GROUP BY key
          HAVING SUM(CASE WHEN current = 1 THEN 1 ELSE 0 END) = 1
        )
        SELECT facts.id FROM facts JOIN usable USING (key);
        """
    )
    rows = connection.execute("SELECT id FROM joined").fetchall()
finally:
    connection.close()
if rows != [("f1",)]:
    raise SystemExit(f"grader SQLite CTE/view probe failed: {rows!r}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(
    callable(value)
    for value in (
        grouped_observations,
        load_private_score,
        source_files_unchanged,
        explicit_external_action_claims,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "sqlite": "cte_view_passed",
            "yaml": "passed",
            "grader_api": "passed",
        },
        sort_keys=True,
    )
)
