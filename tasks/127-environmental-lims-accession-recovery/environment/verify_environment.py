#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

trust = "synthetic-lims-event-key"
event = {"event_id": "EVT-RECV-042", "temperature_c": "8.1"}
signature = hashlib.sha256(json.dumps(event, sort_keys=True).encode() + trust.encode()).hexdigest()
lines = [json.dumps({**event, "signature": signature}), json.dumps({**event, "signature": signature})]
records = [json.loads(line) for line in lines]
unique = {row["event_id"]: row for row in records}
if len(unique) != 1 or unique[event["event_id"]]["signature"] != signature:
    raise SystemExit("signed custody-event dedup probe failed")

received = datetime.fromisoformat("2026-08-19T10:00:00+00:00")
signed = datetime.fromisoformat("2026-08-19T11:15:00+00:00")
if (signed - received).total_seconds() != 75 * 60 or received.tzinfo != timezone.utc:
    raise SystemExit("late custody-signature grace-window probe failed")
if Decimal(event["temperature_c"]) <= Decimal("6.0"):
    raise SystemExit("LIMS temperature-boundary probe failed")

with tempfile.TemporaryDirectory(prefix="hb-lims-probe-") as temporary:
    database = Path(temporary) / "lims.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "CREATE TABLE samples(id TEXT PRIMARY KEY, state TEXT, analysis_started INTEGER); INSERT INTO samples VALUES('SMP-26-042', 'received', 0);"
        )
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE samples SET state='partial' WHERE id='SMP-26-042'")
        connection.rollback()
        restored = connection.execute("SELECT state FROM samples").fetchone()[0]
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE samples SET state='quarantine_temperature' WHERE id='SMP-26-042'")
        connection.commit()
        row = connection.execute("SELECT state, analysis_started FROM samples").fetchone()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT state FROM samples").fetchone()[0]
    finally:
        readonly.close()
    if restored != "received" or row != ("quarantine_temperature", 0) or reread != row[0]:
        raise SystemExit("SQLite LIMS recovery/read-only replay probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("LIMS state hash probe failed")

print(json.dumps({"python3": "3.12", "signed_jsonl": "passed", "utc_grace": "passed", "decimal": "passed", "sqlite": sqlite3.sqlite_version, "sha256": "passed"}, sort_keys=True))
