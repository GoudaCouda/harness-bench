#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


if sys.version_info[:2] != (3, 12):
    fail(
        "task 088 requires CPython 3.12 in the shared agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

connection = sqlite3.connect(":memory:")
try:
    connection.executescript(
        """
        CREATE TABLE dimension(key TEXT, current INTEGER, value REAL);
        INSERT INTO dimension VALUES ('a', 0, 1.0), ('a', 1, 2.0), ('b', 1, 3.0);
        CREATE VIEW resolved AS
        WITH grouped AS (
          SELECT key,
                 SUM(CASE WHEN current = 1 THEN 1 ELSE 0 END) AS current_count,
                 MAX(CASE WHEN current = 1 THEN value END) AS current_value
          FROM dimension GROUP BY key
        )
        SELECT key, current_value FROM grouped WHERE current_count = 1;
        """
    )
    rows = connection.execute("SELECT key, current_value FROM resolved ORDER BY key").fetchall()
finally:
    connection.close()
if rows != [("a", 2.0), ("b", 3.0)]:
    fail(f"SQLite grouped-view probe failed: {rows!r}")

probe = subprocess.run(
    ["python3", "-B", "-c", "import csv,json,pathlib,sqlite3; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    fail(f"python3/stdlib probe failed: {probe.stderr.strip()}")

print(
    json.dumps(
        {
            "python3": "3.12",
            "sqlite": "grouped_view_passed",
            "stdlib": [csv.__name__, "json", "pathlib", sqlite3.__name__],
        },
        sort_keys=True,
    )
)
