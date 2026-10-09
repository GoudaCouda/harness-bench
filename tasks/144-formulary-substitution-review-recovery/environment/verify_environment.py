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
events = [
    json.loads(line)
    for line in (
        '{"delivery_id":"D2","event_id":"E1","source_sequence":2}\n'
        '{"delivery_id":"D1","event_id":"E1","source_sequence":1}\n'
    ).splitlines()
]
if [row["delivery_id"] for row in sorted(events, key=lambda row: row["source_sequence"])] != ["D1", "D2"]:
    raise SystemExit("formulary event ordering probe failed")
if datetime.fromisoformat("2026-08-19T00:00:00+00:00").tzinfo != timezone.utc:
    raise SystemExit("formulary temporal policy probe failed")
if len(hashlib.sha256(json.dumps(events, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("formulary source hash probe failed")
with tempfile.TemporaryDirectory(prefix="hb-formulary-probe-") as temporary:
    database = Path(temporary) / "formulary.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE prescriptions(id TEXT PRIMARY KEY, state TEXT)")
        connection.execute("CREATE TABLE journal(id TEXT PRIMARY KEY, before_state TEXT, restored INTEGER)")
        connection.execute("INSERT INTO prescriptions VALUES ('RX-1', 'partial')")
        connection.execute("INSERT INTO journal VALUES ('J1', 'pending_review', 0)")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE prescriptions SET state=(SELECT before_state FROM journal WHERE id='J1') WHERE id='RX-1'")
        connection.execute("UPDATE journal SET restored=1 WHERE id='J1'")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT state FROM prescriptions WHERE id='RX-1'").fetchone()
    if row != ("pending_review",):
        raise SystemExit("SQLite formulary recovery probe failed")
print(json.dumps({
    "python3": "3.12",
    "event_order": "passed",
    "temporal_policy": "passed",
    "sha256": "passed",
    "sqlite_transaction": "passed",
    "sqlite_read_only": "passed",
}, sort_keys=True))
