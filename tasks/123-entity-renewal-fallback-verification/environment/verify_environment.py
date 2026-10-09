#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

if date.fromisoformat("2026-08-19") + timedelta(days=30) != date(2026, 9, 18):
    raise SystemExit("renewal effective-date arithmetic probe failed")

trust = "synthetic-registry-key"
payload = {"vendor_id": "VND-ALP-17", "version": 4}
signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode() + trust.encode()).hexdigest()
line = json.dumps({**payload, "signature": signature})
parsed = json.loads(line)
if parsed["signature"] != signature or len(signature) != 64:
    raise SystemExit("JSONL signature verification probe failed")

with tempfile.TemporaryDirectory(prefix="hb-vendor-renewal-probe-") as temporary:
    database = Path(temporary) / "vendor_master.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "CREATE TABLE vendors(id TEXT PRIMARY KEY, state TEXT); INSERT INTO vendors VALUES('VND-ALP-17', 'before');"
        )
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE vendors SET state='partial' WHERE id='VND-ALP-17'")
        connection.rollback()
        restored = connection.execute("SELECT state FROM vendors").fetchone()[0]
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE vendors SET state='staged_review' WHERE id='VND-ALP-17'")
        connection.commit()
        committed = connection.execute("SELECT state FROM vendors").fetchone()[0]
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT state FROM vendors").fetchone()[0]
    finally:
        readonly.close()
    if (restored, committed, reread) != ("before", "staged_review", "staged_review"):
        raise SystemExit("SQLite journal recovery/commit replay probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("vendor master hash probe failed")

print(json.dumps({"python3": "3.12", "date": "passed", "jsonl_signature": "passed", "sqlite": sqlite3.sqlite_version, "sha256": "passed"}, sort_keys=True))
