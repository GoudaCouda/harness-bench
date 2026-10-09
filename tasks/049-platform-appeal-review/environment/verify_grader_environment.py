#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
if sqlite3.sqlite_version_info < (3, 40):
    raise SystemExit(f"expected grader SQLite >=3.40, found {sqlite3.sqlite_version}")

with tempfile.TemporaryDirectory() as temporary:
    database = Path(temporary) / "candidate.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE queue(case_id TEXT PRIMARY KEY,status TEXT)")
        connection.execute("INSERT INTO queue VALUES('A-01','staged_for_governance_review')")
        connection.commit()
    uri = f"file:{database}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        row = connection.execute("SELECT case_id,status FROM queue").fetchone()
    if row != ("A-01", "staged_for_governance_review"):
        raise SystemExit(f"read-only grader replay probe failed: {row!r}")

print(json.dumps({"python3": "3.10", "sqlite3": sqlite3.sqlite_version, "readonly_replay": "passed"}, sort_keys=True))
