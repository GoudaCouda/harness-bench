#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
if sqlite3.sqlite_version != "3.40.1":
    raise SystemExit(f"expected SQLite 3.40.1, found {sqlite3.sqlite_version}")

connection = sqlite3.connect(":memory:")
try:
    connection.executescript(
        "CREATE TABLE source(id INTEGER PRIMARY KEY, value TEXT NOT NULL);"
        "INSERT INTO source(value) VALUES ('kept');"
    )
    denied = []

    def authorizer(action, _arg1, _arg2, _database, _source):
        if action == sqlite3.SQLITE_UPDATE and _arg1 == "source":
            denied.append(action)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    connection.set_authorizer(authorizer)
    try:
        connection.execute("UPDATE source SET value = 'changed'")
    except sqlite3.DatabaseError:
        pass
    else:
        raise SystemExit("sqlite3 authorizer did not deny source-table update")
    connection.set_authorizer(lambda *_args: sqlite3.SQLITE_OK)
    row = connection.execute("SELECT id, value FROM source").fetchone()
finally:
    connection.close()

if row != (1, "kept") or not denied:
    raise SystemExit("grader SQLite safety probe failed")

print(json.dumps({
    "python3": "3.10",
    "sqlite3": sqlite3.sqlite_version,
    "authorizer": "passed",
}, sort_keys=True))
