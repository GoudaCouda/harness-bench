#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

deliveries = [
    {"event_id": "evt-2", "provider_sequence": 2},
    {"event_id": "evt-1", "provider_sequence": 1},
    {"event_id": "evt-2", "provider_sequence": 2},
]
duplicate_ids = sorted(key for key, count in Counter(row["event_id"] for row in deliveries).items() if count > 1)
if duplicate_ids != ["evt-2"] or [row["event_id"] for row in sorted(deliveries[:2], key=lambda row: row["provider_sequence"])] != ["evt-1", "evt-2"]:
    raise SystemExit("webhook ordering/deduplication probe failed")

observed = datetime.fromisoformat("2026-08-18T12:00:00Z").astimezone(timezone.utc)
if observed.isoformat() != "2026-08-18T12:00:00+00:00":
    raise SystemExit("UTC event-time probe failed")

with tempfile.TemporaryDirectory(prefix="hb-entitlement-probe-") as temporary:
    database = Path(temporary) / "billing.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;"
            "CREATE TABLE journal(sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE);"
            "INSERT INTO journal VALUES(1, 'evt-1');"
            "COMMIT;"
        )
        row = connection.execute("SELECT sequence, event_id FROM journal").fetchone()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT sequence, event_id FROM journal").fetchone()
    finally:
        readonly.close()
    if row != (1, "evt-1") or reread != row:
        raise SystemExit("SQLite transaction/read-only replay probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("SQLite evidence hash probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "jsonl_event_replay": "passed",
            "datetime_utc": "passed",
            "sqlite_transaction": "passed",
            "sha256": "passed",
        },
        sort_keys=True,
    )
)
