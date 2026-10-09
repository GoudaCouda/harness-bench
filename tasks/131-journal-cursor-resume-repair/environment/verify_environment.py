#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
records = [json.loads(line) for line in (
    '{"event_id":"e1","delta_cents":100}\n'
    '{"event_id":"e1","delta_cents":100}\n'
    '{"event_id":"e2","delta_cents":-25}\n'
).splitlines()]
seen = set()
unique = [row for row in records if not (row["event_id"] in seen or seen.add(row["event_id"]))]
if [row["event_id"] for row in unique] != ["e1", "e2"] or sum(row["delta_cents"] for row in unique) != 75:
    raise SystemExit("exact-once JSONL replay probe failed")
with tempfile.TemporaryDirectory(prefix="hb-journal-cursor-probe-") as temporary:
    database = Path(temporary) / "projection.db"
    with sqlite3.connect(database) as connection:
        connection.executescript("CREATE TABLE accounts(id TEXT PRIMARY KEY, balance INTEGER); CREATE TABLE applied(event_id TEXT PRIMARY KEY); INSERT INTO accounts VALUES ('a', 100);")
        connection.execute("BEGIN IMMEDIATE")
        inserted = connection.execute("INSERT OR IGNORE INTO applied VALUES ('e2')").rowcount
        if inserted:
            connection.execute("UPDATE accounts SET balance=balance-25 WHERE id='a'")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        inserted_again = connection.execute("INSERT OR IGNORE INTO applied VALUES ('e2')").rowcount
        connection.rollback()
        if inserted_again != 0:
            raise SystemExit("SQLite idempotency-ledger probe failed")
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        balance = connection.execute("SELECT balance FROM accounts").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if (balance, integrity) != (75, "ok"):
        raise SystemExit("SQLite projection/read-only integrity probe failed")
print(json.dumps({"python3": "3.12", "jsonl_exact_once": "passed", "sqlite_transaction": "passed", "sqlite_read_only": "passed", "integrity_check": "passed"}, sort_keys=True))
