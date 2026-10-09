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

inventory = {"on_hand": 20, "available": 9, "reserved": 8, "shipped": 3}
if inventory["available"] + inventory["reserved"] + inventory["shipped"] != inventory["on_hand"]:
    raise SystemExit("inventory accounting closure probe failed")

with tempfile.TemporaryDirectory(prefix="hb-wms-probe-") as temporary:
    database = Path(temporary) / "warehouse.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;"
            "CREATE TABLE inventory(sku TEXT PRIMARY KEY, on_hand INTEGER, available INTEGER, reserved INTEGER, shipped INTEGER);"
            "CREATE TABLE reservations(reservation_id TEXT PRIMARY KEY, status TEXT);"
            "INSERT INTO inventory VALUES('SKU-A', 20, 9, 8, 3);"
            "INSERT INTO reservations VALUES('RSV-200', 'shipped');"
            "COMMIT;"
        )
        row = connection.execute("SELECT on_hand, available, reserved, shipped FROM inventory").fetchone()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT reservation_id, status FROM reservations").fetchone()
    finally:
        readonly.close()
    if row != (20, 9, 8, 3) or reread != ("RSV-200", "shipped"):
        raise SystemExit("SQLite WMS transaction/read-only replay probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("warehouse state hash probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "inventory_accounting": "passed",
            "sqlite_transaction": "passed",
            "sha256": "passed",
        },
        sort_keys=True,
    )
)
