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
sqlite_version = tuple(int(part) for part in sqlite3.sqlite_version.split(".")[:2])
if not (sqlite_version >= (3, 40) and sqlite_version < (4, 0)):
    raise SystemExit(f"expected SQLite >=3.40,<4, found {sqlite3.sqlite_version}")

with tempfile.TemporaryDirectory(prefix="hb001-env-") as directory:
    database = Path(directory) / "probe.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE journal (id TEXT PRIMARY KEY, restored INTEGER)")
        connection.execute("INSERT INTO journal VALUES ('J-DNS-PROBE', 0)")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE journal SET restored = 1 WHERE id = 'J-DNS-PROBE'")
        connection.rollback()
        rolled_back = connection.execute(
            "SELECT restored FROM journal WHERE id = 'J-DNS-PROBE'"
        ).fetchone()[0]
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE journal SET restored = 1 WHERE id = 'J-DNS-PROBE'")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        committed = connection.execute(
            "SELECT restored FROM journal WHERE id = 'J-DNS-PROBE'"
        ).fetchone()[0]

if rolled_back != 0 or committed != 1:
    raise SystemExit("SQLite transaction or read-only URI behavior is unavailable")
digest = hashlib.sha256(json.dumps({"committed": committed}).encode()).hexdigest()
print(json.dumps({"python": "3.12", "sqlite3": sqlite3.sqlite_version, "transaction_probe_sha256": digest}, sort_keys=True))
