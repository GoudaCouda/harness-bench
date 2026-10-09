#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
records = [json.loads(line) for line in (
    '{"event_id":"USE-1","version":1,"cents":"12.50"}\n'
    '{"event_id":"USE-1","version":2,"cents":"-2.50"}\n'
).splitlines()]
latest = max(records, key=lambda row: row["version"])
if latest["version"] != 2 or Decimal(latest["cents"]) != Decimal("-2.50"):
    raise SystemExit("versioned signed-usage JSONL probe failed")
with tempfile.TemporaryDirectory(prefix="hb-royalty-probe-") as temporary:
    database = Path(temporary) / "ledger.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE allocations(event_id TEXT PRIMARY KEY, cents INTEGER)")
        connection.execute("INSERT INTO allocations VALUES ('partial', 60000)")
        connection.commit()
        try:
            connection.execute("BEGIN")
            connection.execute("DELETE FROM allocations WHERE event_id='partial'")
            connection.execute("INSERT INTO allocations VALUES ('final', 185000)")
            raise RuntimeError("interrupt")
        except RuntimeError:
            connection.rollback()
        if connection.execute("SELECT SUM(cents) FROM allocations").fetchone()[0] != 60000:
            raise SystemExit("SQLite interrupted-allocation rollback probe failed")
        connection.execute("BEGIN")
        connection.execute("DELETE FROM allocations")
        connection.execute("INSERT INTO allocations VALUES ('final', 185000)")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT event_id, cents FROM allocations").fetchall()
    if rows != [("final", 185000)]:
        raise SystemExit("SQLite atomic royalty-ledger recovery probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("royalty-ledger hash probe failed")
print(json.dumps({"python3": "3.12", "jsonl_versioning": "passed", "decimal_signed_amount": "passed", "sqlite_transaction": "passed", "sqlite_read_only": "passed", "sha256": "passed"}, sort_keys=True))
