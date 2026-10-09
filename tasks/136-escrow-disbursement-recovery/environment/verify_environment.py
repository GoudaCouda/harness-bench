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
document = {"instruction_id": "INS-1", "account_suffix": "1122", "amount_cents": 7200000, "signed": True}
encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
if len(hashlib.sha256(encoded).hexdigest()) != 64:
    raise SystemExit("escrow document hash probe failed")
with tempfile.TemporaryDirectory(prefix="hb-escrow-probe-") as temporary:
    database = Path(temporary) / "escrow.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE closings(id TEXT PRIMARY KEY, wire INTEGER, disbursed INTEGER)")
        connection.execute("CREATE TABLE journal(id TEXT PRIMARY KEY, restored INTEGER)")
        connection.execute("INSERT INTO closings VALUES ('ESC-1', 10000000, 0)")
        connection.execute("INSERT INTO journal VALUES ('old', 0)")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE journal SET restored=1 WHERE id='old'")
        connection.execute("UPDATE closings SET disbursed=7200000 WHERE id='ESC-1'")
        connection.rollback()
        if connection.execute("SELECT disbursed FROM closings").fetchone()[0] != 0:
            raise SystemExit("SQLite escrow rollback probe failed")
        connection.execute("UPDATE journal SET restored=1 WHERE id='old'")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        state = connection.execute("SELECT wire, disbursed FROM closings").fetchone()
    if state != (10000000, 0):
        raise SystemExit("SQLite escrow read-only boundary probe failed")
if 7200000 + 2720000 + 80000 != 10000000:
    raise SystemExit("integer-cent escrow conservation probe failed")
print(json.dumps({"python3": "3.12", "document_sha256": "passed", "sqlite_transaction": "passed", "sqlite_read_only": "passed", "funds_conservation": "passed"}, sort_keys=True))
