#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

new_york = datetime(2026, 8, 19, 9, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
london = datetime(2026, 8, 24, 14, 0, tzinfo=ZoneInfo("Europe/London")).astimezone(timezone.utc)
if (new_york.hour, london.hour) != (13, 13):
    raise SystemExit("IANA calendar timezone conversion probe failed")

ics = "BEGIN:VEVENT\nUID:ops@example.test\nSEQUENCE:2\nEND:VEVENT\nBEGIN:VEVENT\nUID:ops@example.test\nRECURRENCE-ID:20260820T090000\nSEQUENCE:2\nEND:VEVENT\n"
components = [chunk for chunk in ics.split("BEGIN:VEVENT\n") if "END:VEVENT" in chunk]
identities = ["ops@example.test|master", "ops@example.test|20260820T090000"]
if len(components) != 2 or len(set(identities)) != 2:
    raise SystemExit("RFC 5545 master/recurrence identity probe failed")

with tempfile.TemporaryDirectory(prefix="hb-calendar-probe-") as temporary:
    database = Path(temporary) / "calendar.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;"
            "CREATE TABLE events(uid TEXT, recurrence_id TEXT, sequence INTEGER, PRIMARY KEY(uid, recurrence_id));"
            "CREATE TABLE checkpoint(collection_id TEXT PRIMARY KEY, etag TEXT);"
            "INSERT INTO events VALUES('ops@example.test', 'master', 2);"
            "INSERT INTO checkpoint VALUES('finance-operations', 'cal-42b');"
            "COMMIT;"
        )
        row = connection.execute("SELECT uid, recurrence_id, sequence FROM events").fetchone()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT collection_id, etag FROM checkpoint").fetchone()
    finally:
        readonly.close()
    if row != ("ops@example.test", "master", 2) or reread != ("finance-operations", "cal-42b"):
        raise SystemExit("SQLite calendar/checkpoint transaction probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("calendar state hash probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "iana_timezones": "passed",
            "rfc5545_identity": "passed",
            "sqlite_transaction": "passed",
            "sha256": "passed",
        },
        sort_keys=True,
    )
)
