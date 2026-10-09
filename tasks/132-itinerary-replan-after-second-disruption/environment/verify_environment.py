#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
departure = datetime.fromisoformat("2026-10-16T22:15:00-07:00")
arrival = datetime.fromisoformat("2026-10-17T08:45:00-04:00")
if int((arrival - departure).total_seconds()) != 27000:
    raise SystemExit("offset-aware itinerary arithmetic probe failed")
payload = {"snapshot_id": "INV-1", "offers": ["O-F", "O-H"]}
signature = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
if len(signature) != 64:
    raise SystemExit("signed inventory hash probe failed")
with tempfile.TemporaryDirectory(prefix="hb-itinerary-probe-") as temporary:
    database = Path(temporary) / "travel.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE itinerary_objects(id TEXT PRIMARY KEY, status TEXT)")
        connection.execute("CREATE TABLE recovery_journal(id TEXT PRIMARY KEY, restored INTEGER)")
        connection.execute("INSERT INTO itinerary_objects VALUES ('AIR-1', 'preserved')")
        connection.execute("INSERT INTO recovery_journal VALUES ('old', 0)")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE recovery_journal SET restored=1 WHERE id='old'")
        connection.execute("INSERT INTO itinerary_objects VALUES ('AIR-2', 'proposed')")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        state = connection.execute("SELECT id, status FROM itinerary_objects ORDER BY id").fetchall()
    if state != [("AIR-1", "preserved"), ("AIR-2", "proposed")]:
        raise SystemExit("SQLite itinerary transaction/read-only probe failed")
    ics = Path(temporary) / "itinerary.ics"
    ics.write_text("BEGIN:VCALENDAR\nBEGIN:VEVENT\nSTATUS:TENTATIVE\nEND:VEVENT\nEND:VCALENDAR\n", encoding="utf-8")
    if "STATUS:TENTATIVE" not in ics.read_text(encoding="utf-8"):
        raise SystemExit("RFC 5545 artifact probe failed")
print(json.dumps({"python3": "3.12", "timezone": "passed", "sha256": "passed", "sqlite_transaction": "passed", "sqlite_read_only": "passed", "rfc5545": "passed"}, sort_keys=True))
