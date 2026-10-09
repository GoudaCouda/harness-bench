#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
with sqlite3.connect(":memory:") as connection:
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("CREATE TABLE ledger (id TEXT PRIMARY KEY)")
    connection.execute("INSERT INTO ledger VALUES ('probe')")
    connection.commit()
    if connection.execute("SELECT id FROM ledger").fetchone() != ("probe",):
        raise SystemExit("SQLite transaction probe failed")
print(json.dumps({"python": "3.12", "sqlite": sqlite3.sqlite_version}, sort_keys=True))
