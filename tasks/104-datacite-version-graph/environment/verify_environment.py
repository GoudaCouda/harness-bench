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

with tempfile.TemporaryDirectory(prefix="hb-datacite-probe-") as temporary:
    database = Path(temporary) / "repository.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;"
            "CREATE TABLE records(doi TEXT PRIMARY KEY, state TEXT NOT NULL);"
            "INSERT INTO records VALUES('10.data/probe.v1', 'findable');"
            "COMMIT;"
        )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        row = readonly.execute("SELECT doi, state FROM records").fetchone()
    finally:
        readonly.close()
    if integrity != "ok" or row != ("10.data/probe.v1", "findable"):
        raise SystemExit("SQLite transaction or read-only URI probe failed")
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    if len(digest) != 64:
        raise SystemExit("database hashing probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "sqlite": sqlite3.sqlite_version,
            "transaction": "passed",
            "readonly_uri": "passed",
        },
        sort_keys=True,
    )
)
