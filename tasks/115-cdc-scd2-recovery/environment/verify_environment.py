#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

batch = '{"event_id":"EV-2","version":2}\n{"event_id":"EV-1","version":1}\n{"event_id":"EV-2","version":2}\n'
events = [json.loads(line) for line in batch.splitlines()]
unique = {row["event_id"]: row for row in events}
if sorted(unique, key=lambda key: unique[key]["version"]) != ["EV-1", "EV-2"]:
    raise SystemExit("CDC JSONL ordering/deduplication probe failed")

holds = list(csv.DictReader(io.StringIO("customer_id,hold_id\nC003,HOLD-77\n")))
if holds != [{"customer_id": "C003", "hold_id": "HOLD-77"}]:
    raise SystemExit("retention-hold CSV probe failed")

with tempfile.TemporaryDirectory(prefix="hb-scd2-probe-") as temporary:
    database = Path(temporary) / "warehouse.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE history(customer_id TEXT, version INTEGER, valid_to TEXT, PRIMARY KEY(customer_id, version))")
        connection.execute("CREATE TABLE current(customer_id TEXT PRIMARY KEY, version INTEGER)")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT INTO history VALUES('C001', 1, NULL)")
        connection.execute("INSERT INTO current VALUES('C001', 1)")
        connection.commit()
        history = connection.execute("SELECT * FROM history").fetchone()
        current = connection.execute("SELECT * FROM current").fetchone()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT customer_id, version FROM current").fetchone()
    finally:
        readonly.close()
    if history != ("C001", 1, None) or current != ("C001", 1) or reread != current:
        raise SystemExit("SQLite SCD2 transaction/read-only replay probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("warehouse evidence hash probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "cdc_jsonl": "passed",
            "retention_csv": "passed",
            "sqlite_scd2_transaction": "passed",
            "sha256": "passed",
        },
        sort_keys=True,
    )
)
