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
with tempfile.TemporaryDirectory(prefix="hb-crm-agent-probe-") as temporary:
    database = Path(temporary) / "crm.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE accounts(id TEXT PRIMARY KEY, status TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE contacts(id TEXT PRIMARY KEY, account_id TEXT, email_opt_out INTEGER)"
        )
        connection.executemany(
            "INSERT INTO accounts VALUES (?, ?)",
            [("A-100", "active"), ("A-101", "active")],
        )
        connection.execute("INSERT INTO contacts VALUES ('C-1', 'A-101', 1)")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE contacts SET account_id='A-100' WHERE account_id='A-101'"
        )
        connection.execute(
            "UPDATE accounts SET status='merged_into:A-100' WHERE id='A-101'"
        )
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        accounts = connection.execute("SELECT id,status FROM accounts ORDER BY id").fetchall()
        contacts = connection.execute("SELECT id,account_id,email_opt_out FROM contacts").fetchall()
state = {"accounts": accounts, "contacts": contacts}
payload = json.dumps(state, sort_keys=True).encode()
if contacts != [("C-1", "A-100", 1)]:
    raise SystemExit("CRM transaction/consent probe failed")
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("CRM logical-state digest probe failed")
print(json.dumps({"python3": "3.12", "sqlite_transaction": "passed", "sqlite_read_only": "passed", "logical_digest": "passed"}, sort_keys=True))
