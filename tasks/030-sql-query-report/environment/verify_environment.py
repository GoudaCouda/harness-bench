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

source = """
CREATE TABLE orders(order_id TEXT PRIMARY KEY, amount NUMERIC NOT NULL);
INSERT INTO orders VALUES ('O-1', 10.25), ('O-2', 5.75);
"""
report = """
DROP VIEW IF EXISTS report_total;
CREATE VIEW report_total AS
SELECT COUNT(*) AS order_count, ROUND(SUM(amount), 2) AS amount
FROM orders;
"""
connection = sqlite3.connect(":memory:")
try:
    connection.executescript(source)
    before = connection.execute(
        "SELECT order_id, amount FROM orders ORDER BY order_id"
    ).fetchall()
    connection.executescript(report)
    connection.executescript(report)
    row = connection.execute(
        "SELECT order_count, amount FROM report_total"
    ).fetchone()
    after = connection.execute(
        "SELECT order_id, amount FROM orders ORDER BY order_id"
    ).fetchall()
finally:
    connection.close()

if row != (2, 16.0):
    raise SystemExit(f"SQLite view/idempotency probe failed: {row!r}")
if after != before:
    raise SystemExit("SQLite report probe changed source rows")

required_constants = (
    "SQLITE_DELETE",
    "SQLITE_INSERT",
    "SQLITE_UPDATE",
    "SQLITE_PRAGMA",
)
missing = [name for name in required_constants if not hasattr(sqlite3, name)]
if missing:
    raise SystemExit(f"sqlite3 authorizer constants missing: {missing}")
