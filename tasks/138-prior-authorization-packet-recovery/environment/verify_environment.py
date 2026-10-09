#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
events = [json.loads(line) for line in (
    '{"event_id":"E1","sequence":1,"member_id":"M1"}\n'
    '{"event_id":"E1","sequence":1,"member_id":"M1"}\n'
    '{"event_id":"E2","sequence":2,"member_id":"WRONG"}\n'
).splitlines()]
unique = {}
for row in events:
    unique.setdefault(row["event_id"], row)
if list(unique) != ["E1", "E2"] or unique["E2"]["member_id"] != "WRONG":
    raise SystemExit("prior-auth event dedup/identity probe failed")
document = {"member_id": "M1", "signed": True, "expires": "2026-09-30"}
if date.fromisoformat(document["expires"]) <= date.fromisoformat("2026-09-01"):
    raise SystemExit("prior-auth evidence date probe failed")
if len(hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("prior-auth evidence hash probe failed")
with tempfile.TemporaryDirectory(prefix="hb-prior-auth-probe-") as temporary:
    database = Path(temporary) / "portal.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE attempts(id TEXT PRIMARY KEY, state TEXT, payer_ref TEXT)")
        connection.execute("CREATE TABLE journal(id TEXT PRIMARY KEY, restored INTEGER)")
        connection.execute("INSERT INTO attempts VALUES ('PA-OLD', 'submitted', 'REF-1')")
        connection.execute("INSERT INTO journal VALUES ('interrupted', 0)")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE journal SET restored=1")
        connection.execute("INSERT INTO attempts VALUES ('PA-NEW', 'queued_local', NULL)")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT id, state, payer_ref FROM attempts ORDER BY id").fetchall()
    if rows != [("PA-NEW", "queued_local", None), ("PA-OLD", "submitted", "REF-1")]:
        raise SystemExit("SQLite prior-auth recovery/boundary probe failed")
print(json.dumps({"python3": "3.12", "jsonl_identity": "passed", "date": "passed", "sha256": "passed", "sqlite_transaction": "passed", "sqlite_read_only": "passed"}, sort_keys=True))
