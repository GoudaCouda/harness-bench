#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
if sqlite3.sqlite_version_info < (3, 40):
    raise SystemExit(f"expected SQLite >=3.40, found {sqlite3.sqlite_version}")

with tempfile.TemporaryDirectory() as temporary:
    database = Path(temporary) / "appeals.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            "CREATE TABLE queue(case_id TEXT PRIMARY KEY,status TEXT);"
            "CREATE TABLE journal(case_id TEXT PRIMARY KEY,before_json TEXT,restored INTEGER);"
            "INSERT INTO queue VALUES('A-01','partially_applied');"
            "INSERT INTO journal VALUES('A-01','{\"status\":\"pending_review\"}',0);"
        )
        connection.execute("BEGIN IMMEDIATE")
        before = json.loads(connection.execute(
            "SELECT before_json FROM journal WHERE case_id='A-01'"
        ).fetchone()[0])
        connection.execute("UPDATE queue SET status=? WHERE case_id='A-01'", (before["status"],))
        connection.execute("UPDATE journal SET restored=1 WHERE case_id='A-01'")
        connection.commit()
        state = connection.execute(
            "SELECT q.status,j.restored FROM queue q JOIN journal j USING(case_id)"
        ).fetchone()
    payload = json.dumps({"case_id": "A-01", "state": state}, sort_keys=True).encode()
    if state != ("pending_review", 1) or len(hashlib.sha256(payload).hexdigest()) != 64:
        raise SystemExit(f"transactional recovery probe failed: {state!r}")

print(json.dumps({"python3": "3.12", "sqlite3": sqlite3.sqlite_version, "queue_recovery": "passed"}, sort_keys=True))
