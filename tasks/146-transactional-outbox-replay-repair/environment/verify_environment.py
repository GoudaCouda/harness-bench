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
with tempfile.TemporaryDirectory(prefix="hb-outbox-agent-probe-") as temporary:
    database = Path(temporary) / "outbox.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE outbox(event_id TEXT PRIMARY KEY, aggregate_id TEXT, sequence INTEGER)"
        )
        connection.execute(
            "CREATE TABLE receipts(event_id TEXT, attempt INTEGER, outcome TEXT)"
        )
        connection.executemany(
            "INSERT INTO outbox VALUES (?, ?, ?)",
            [("event-1", "order-1", 1), ("event-2", "order-1", 2)],
        )
        connection.execute("INSERT INTO receipts VALUES ('event-1', 1, 'unknown')")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT event_id FROM outbox ORDER BY aggregate_id, sequence"
        ).fetchall()
        receipt = connection.execute(
            "SELECT outcome FROM receipts WHERE event_id='event-1'"
        ).fetchone()
payload = json.dumps(
    {"rows": [row[0] for row in rows], "receipt": receipt[0]},
    sort_keys=True,
).encode()
if json.loads(payload) != {
    "receipt": "unknown",
    "rows": ["event-1", "event-2"],
}:
    raise SystemExit("transactional outbox SQLite/JSON probe failed")
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("transactional outbox hash probe failed")
print(json.dumps({"python3": "3.12", "sqlite": "passed", "json": "passed", "sha256": "passed"}, sort_keys=True))
