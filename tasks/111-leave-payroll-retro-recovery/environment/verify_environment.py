#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

start = datetime.fromisoformat("2026-08-10T22:30:00-04:00")
end = datetime.fromisoformat("2026-08-11T02:30:00-04:00")
if (end - start).total_seconds() / 3600 != 4:
    raise SystemExit("offset-aware payroll interval probe failed")

with tempfile.TemporaryDirectory(prefix="hb-payroll-probe-") as temporary:
    database = Path(temporary) / "payroll.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;"
            "CREATE TABLE journal(sequence INTEGER PRIMARY KEY, adjustment_id TEXT UNIQUE);"
            "INSERT INTO journal VALUES(1, 'RA-1');"
            "COMMIT;"
        )
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        row = readonly.execute("SELECT sequence, adjustment_id FROM journal").fetchone()
    finally:
        readonly.close()
    if row != (1, "RA-1") or len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("SQLite journal/read-only snapshot probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "datetime_offset": "passed",
            "sqlite_transaction": "passed",
            "sqlite_readonly": "passed",
        },
        sort_keys=True,
    )
)
