#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

with tempfile.TemporaryDirectory(prefix="hb-162-sqlite-") as directory:
    database = Path(directory) / "degree.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE transcript(
                student_id TEXT NOT NULL,
                course TEXT NOT NULL,
                term TEXT NOT NULL,
                grade TEXT NOT NULL
            );
            INSERT INTO transcript VALUES ('S-42', 'CS-101', '2025-FALL', 'A');
            """
        )
    uri = f"file:{database}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        row = connection.execute(
            "SELECT course, grade FROM transcript WHERE student_id = ?",
            ("S-42",),
        ).fetchone()
        if row != ("CS-101", "A"):
            raise SystemExit("SQLite degree-record read probe failed")
        try:
            connection.execute(
                "INSERT INTO transcript VALUES ('S-42','CS-999','2026','A')"
            )
        except sqlite3.OperationalError:
            pass
        else:
            raise SystemExit("SQLite read-only boundary probe failed")

print(json.dumps({
    "python3": "3.12",
    "sqlite": sqlite3.sqlite_version,
    "transaction": "passed",
    "readonly_uri": "passed",
    "services": "not_required_by_task_contract",
}, sort_keys=True))
