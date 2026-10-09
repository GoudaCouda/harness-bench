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
deliveries = [json.loads(line) for line in (
    '{"delivery_id":"D2","event_id":"E1","sequence":2}\n'
    '{"delivery_id":"D1","event_id":"E1","sequence":1}\n'
    '{"delivery_id":"D3","event_id":"E2","sequence":3}\n'
).splitlines()]
first_by_event = {}
for row in deliveries:
    first_by_event.setdefault(row["event_id"], row)
ordered = sorted(first_by_event.values(), key=lambda row: row["sequence"])
if [row["delivery_id"] for row in ordered] != ["D2", "D3"]:
    raise SystemExit("arrival-authority JSONL deduplication probe failed")
blob = b'{"shipment_id":"SHIP-1","signed":true}\\n'
if len(hashlib.sha256(blob).hexdigest()) != 64:
    raise SystemExit("evidence blob hash probe failed")
with tempfile.TemporaryDirectory(prefix="hb-claims-probe-") as temporary:
    database = Path(temporary) / "claims.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE cases(case_id TEXT PRIMARY KEY, state TEXT, paid INTEGER)")
        connection.execute("CREATE TABLE journal(run_id TEXT PRIMARY KEY, status TEXT)")
        connection.execute("INSERT INTO cases VALUES ('CL-1', 'submitted', 1000)")
        connection.execute("INSERT INTO journal VALUES ('interrupted', 'open')")
        connection.commit()
        try:
            connection.execute("BEGIN")
            connection.execute("UPDATE cases SET state='ready' WHERE case_id='CL-1'")
            connection.execute("UPDATE journal SET status='restored' WHERE run_id='interrupted'")
            raise RuntimeError("interrupt")
        except RuntimeError:
            connection.rollback()
        state = connection.execute("SELECT state, paid FROM cases").fetchone()
        if state != ("submitted", 1000):
            raise SystemExit("SQLite protected-claim rollback probe failed")
        connection.execute("UPDATE journal SET status='restored' WHERE run_id='interrupted'")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        if connection.execute("SELECT status FROM journal").fetchone()[0] != "restored":
            raise SystemExit("SQLite claim-journal commit probe failed")
print(json.dumps({"python3": "3.12", "jsonl_event_authority": "passed", "blob_sha256": "passed", "sqlite_transaction": "passed", "sqlite_read_only": "passed"}, sort_keys=True))
