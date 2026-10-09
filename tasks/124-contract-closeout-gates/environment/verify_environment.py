#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

data = "event_id,sequence,effective_date\nEV-3,30,2026-08-15\nEV-1,10,2026-08-01\n"
events = list(csv.DictReader(data.splitlines()))
events.sort(key=lambda row: int(row["sequence"]))
if [row["event_id"] for row in events] != ["EV-1", "EV-3"]:
    raise SystemExit("ordered closeout evidence CSV probe failed")
if date.fromisoformat(events[-1]["effective_date"]) != date(2026, 8, 15):
    raise SystemExit("closeout effective-date probe failed")

with tempfile.TemporaryDirectory(prefix="hb-closeout-probe-") as temporary:
    database = Path(temporary) / "closeout.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "CREATE TABLE audit(seq INTEGER PRIMARY KEY, contract_id TEXT); INSERT INTO audit VALUES(1, 'C-401'); INSERT INTO audit VALUES(2, 'C-402');"
        )
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany("INSERT INTO audit VALUES(?, ?)", [(3, "C-403"), (4, "C-404")])
        connection.commit()
        rows = connection.execute("SELECT seq, contract_id FROM audit ORDER BY seq").fetchall()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
    finally:
        readonly.close()
    if rows[:2] != [(1, "C-401"), (2, "C-402")]:
        raise SystemExit("durable audit-prefix preservation probe failed")
    if reread != 4:
        raise SystemExit("SQLite closeout transaction/read-only replay probe failed")
    if len(hashlib.sha256(json.dumps(rows).encode() + database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("closeout state hash probe failed")

print(json.dumps({"python3": "3.12", "csv_order": "passed", "date": "passed", "sqlite": sqlite3.sqlite_version, "sha256": "passed"}, sort_keys=True))
