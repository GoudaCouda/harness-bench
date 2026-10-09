#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
messages = [
    json.loads(line)
    for line in (
        '{"message_id":"M2","source_sequence":2,"version":2}\n'
        '{"message_id":"M1","source_sequence":1,"version":1}\n'
        '{"message_id":"M1","source_sequence":3,"version":1}\n'
    ).splitlines()
]
ordered = sorted(messages, key=lambda row: (row["source_sequence"], row["message_id"]))
if [row["message_id"] for row in ordered] != ["M1", "M2", "M1"]:
    raise SystemExit("pharmacovigilance source-sequence probe failed")
if len(hashlib.sha256(json.dumps(ordered, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("pharmacovigilance source hash probe failed")
with tempfile.TemporaryDirectory(prefix="hb-pv-probe-") as temporary:
    database = Path(temporary) / "pv.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE cases(id TEXT PRIMARY KEY, version INTEGER)")
        connection.execute("CREATE TABLE journal(id TEXT PRIMARY KEY, before_json TEXT, restored INTEGER)")
        connection.execute("INSERT INTO cases VALUES ('ICSR-1', 2)")
        connection.execute("INSERT INTO journal VALUES ('J1', ?, 0)", (json.dumps({"id": "ICSR-1", "version": 1}),))
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        before = json.loads(connection.execute("SELECT before_json FROM journal WHERE id='J1'").fetchone()[0])
        connection.execute("UPDATE cases SET version=? WHERE id=?", (before["version"], before["id"]))
        connection.execute("UPDATE journal SET restored=1 WHERE id='J1'")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT version FROM cases WHERE id='ICSR-1'").fetchone()
        restored = connection.execute("SELECT restored FROM journal WHERE id='J1'").fetchone()
    if row != (1,) or restored != (1,):
        raise SystemExit("SQLite pharmacovigilance journal recovery probe failed")
print(json.dumps({
    "python3": "3.12",
    "jsonl_order": "passed",
    "sha256": "passed",
    "sqlite_transaction": "passed",
    "sqlite_read_only": "passed",
}, sort_keys=True))
