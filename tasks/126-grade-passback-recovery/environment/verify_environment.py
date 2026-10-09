#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

lines = ['{"event_id":"RES-2","source_sequence":20}', '{"event_id":"RES-1","source_sequence":10}', '{"event_id":"RES-2","source_sequence":20}']
feed = [json.loads(line) for line in lines]
unique = {row["event_id"]: row for row in feed}
ordered = sorted(unique.values(), key=lambda row: row["source_sequence"])
if [row["event_id"] for row in ordered] != ["RES-1", "RES-2"]:
    raise SystemExit("grade feed ordering/dedup probe failed")

submitted = datetime.fromisoformat("2026-08-19T23:59:59+00:00")
deadline = datetime(2026, 8, 20, tzinfo=timezone.utc)
if not submitted < deadline:
    raise SystemExit("UTC late-window boundary probe failed")

with tempfile.TemporaryDirectory(prefix="hb-gradepass-probe-") as temporary:
    database = Path(temporary) / "gradepass.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "CREATE TABLE gradebook(student TEXT, assignment TEXT, score INTEGER, manual_override INTEGER, PRIMARY KEY(student, assignment)); INSERT INTO gradebook VALUES('STU-1', 'ASG-1', 18, 1);"
        )
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE gradebook SET score=0 WHERE manual_override=0")
        connection.rollback()
        restored = connection.execute("SELECT score, manual_override FROM gradebook").fetchone()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT INTO gradebook VALUES('STU-2', 'ASG-1', 17, 0)")
        connection.commit()
        rows = connection.execute("SELECT student, score, manual_override FROM gradebook ORDER BY student").fetchall()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT COUNT(*) FROM gradebook").fetchone()[0]
    finally:
        readonly.close()
    if restored != (18, 1):
        raise SystemExit("manual grade override preservation probe failed")
    if rows != [("STU-1", 18, 1), ("STU-2", 17, 0)]:
        raise SystemExit("SQLite gradebook transaction probe failed")
    if reread != 2:
        raise SystemExit("read-only gradebook replay probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("gradebook state hash probe failed")

print(json.dumps({"python3": "3.12", "jsonl_dedup": "passed", "utc_boundary": "passed", "sqlite": sqlite3.sqlite_version, "override": "passed", "sha256": "passed"}, sort_keys=True))
