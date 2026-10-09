#!/usr/bin/env python3
from __future__ import annotations
import json
import sqlite3
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
with sqlite3.connect(":memory:") as connection:
    connection.execute("CREATE TABLE evidence (id TEXT PRIMARY KEY, seq INTEGER NOT NULL)")
    connection.executemany("INSERT INTO evidence VALUES (?, ?)", [("b", 2), ("a", 1)])
    rows = connection.execute("SELECT id, seq FROM evidence ORDER BY seq").fetchall()
if rows != [("a", 1), ("b", 2)]:
    raise SystemExit("SQLite transaction/query probe failed")
print(json.dumps({"python3": "3.12", "sqlite": sqlite3.sqlite_version}, sort_keys=True))
