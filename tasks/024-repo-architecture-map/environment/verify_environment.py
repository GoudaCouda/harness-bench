#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
sqlite_version = tuple(int(part) for part in sqlite3.sqlite_version.split(".")[:2])
if not (sqlite_version >= (3, 40) and sqlite_version < (4, 0)):
    raise SystemExit(f"expected SQLite >=3.40,<4, found {sqlite3.sqlite_version}")
connection = sqlite3.connect(":memory:")
try:
    connection.execute(
        "create table orders (order_id text primary key, customer text not null, total_cents integer not null)"
    )
    connection.execute(
        "insert into orders(order_id, customer, total_cents) values (?, ?, ?)",
        ("O-1", "Northwind", 1250),
    )
    row = connection.execute(
        "select order_id, customer, total_cents from orders where order_id = ?",
        ("O-1",),
    ).fetchone()
finally:
    connection.close()
if row != ("O-1", "Northwind", 1250):
    raise SystemExit(f"minisvc SQLite smoke probe failed: {row}")
print(json.dumps({"python3": "3.12", "sqlite3": sqlite3.sqlite_version, "row": row}, sort_keys=True))
