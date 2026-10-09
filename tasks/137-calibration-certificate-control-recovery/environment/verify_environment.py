#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
margin = Decimal("1.00") - (abs(Decimal("0.75")) + Decimal("0.25"))
if margin != Decimal("0.00") or margin < 0:
    raise SystemExit("inclusive Decimal guard-band probe failed")
calibrated = datetime.fromisoformat("2026-05-01T10:00:00+00:00")
affected = datetime.fromisoformat("2026-04-15T00:00:00+00:00")
if not affected <= calibrated:
    raise SystemExit("reference recall temporal-scope probe failed")
result = {"job_id": "JOB-1", "error": "0.75", "uncertainty": "0.25"}
if len(hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("measurement attachment hash probe failed")
with tempfile.TemporaryDirectory(prefix="hb-metrology-probe-") as temporary:
    database = Path(temporary) / "calibration.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, certificate_state TEXT)")
        connection.execute("CREATE TABLE journal(id TEXT PRIMARY KEY, restored INTEGER)")
        connection.execute("INSERT INTO jobs VALUES ('JOB-1', 'issued')")
        connection.execute("INSERT INTO journal VALUES ('old', 0)")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE journal SET restored=1")
        connection.execute("UPDATE jobs SET certificate_state='revoked_local' WHERE id='JOB-1'")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        state = connection.execute("SELECT certificate_state FROM jobs").fetchone()[0]
    if state != "revoked_local":
        raise SystemExit("SQLite calibration recovery/read-only probe failed")
print(json.dumps({"python3": "3.12", "decimal_guard_band": "passed", "recall_time": "passed", "sha256": "passed", "sqlite_transaction": "passed", "sqlite_read_only": "passed"}, sort_keys=True))
