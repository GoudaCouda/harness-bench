#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
dataset = {
    "PatientIdentityRemoved": "YES",
    "StudyDate": (datetime.strptime("20260831", "%Y%m%d") + timedelta(days=-37)).strftime("%Y%m%d"),
    "SOPInstanceUID": "2.25.141",
    "PrivateTags": {"0019,1001": "allowed"},
}
payload = b"\0" * 128 + b"DICM" + json.dumps(dataset, sort_keys=True).encode()
parsed = json.loads(payload[132:])
if parsed["StudyDate"] != "20260725" or parsed["PatientIdentityRemoved"] != "YES":
    raise SystemExit("DICOM framing/date-shift probe failed")
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("DICOM hash probe failed")
with tempfile.TemporaryDirectory(prefix="hb-dicom-probe-") as temporary:
    database = Path(temporary) / "imaging.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE runs(id TEXT PRIMARY KEY, status TEXT, external_exports INTEGER)")
        connection.execute("CREATE TABLE journal(id TEXT PRIMARY KEY, restored INTEGER)")
        connection.execute("INSERT INTO runs VALUES ('OLD', 'interrupted', 0)")
        connection.execute("INSERT INTO journal VALUES ('J1', 0)")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE runs SET status='rolled_back' WHERE id='OLD'")
        connection.execute("UPDATE journal SET restored=1 WHERE id='J1'")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT status,external_exports FROM runs WHERE id='OLD'").fetchone()
    if row != ("rolled_back", 0):
        raise SystemExit("SQLite DICOM journal probe failed")
print(json.dumps({
    "python3": "3.12",
    "dicm_framing": "passed",
    "date_shift": "passed",
    "sha256": "passed",
    "sqlite_transaction": "passed",
    "sqlite_read_only": "passed",
}, sort_keys=True))
