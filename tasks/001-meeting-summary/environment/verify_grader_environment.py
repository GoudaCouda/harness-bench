#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import yaml

if sqlite3.sqlite_version != "3.40.1":
    raise SystemExit(f"expected grader SQLite 3.40.1, found {sqlite3.sqlite_version}")
if not str(yaml.__version__).startswith("6."):
    raise SystemExit(f"expected PyYAML 6.x, found {yaml.__version__}")

with tempfile.TemporaryDirectory(prefix="hb001-grader-") as directory:
    database = Path(directory) / "probe.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE zones (zone_name TEXT PRIMARY KEY, serial INTEGER)")
        connection.execute("INSERT INTO zones VALUES ('probe.example', 2026090201)")
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT zone_name, serial FROM zones").fetchone()

if row != ("probe.example", 2026090201):
    raise SystemExit("grader SQLite read-only projection probe failed")
print(json.dumps({"PyYAML": yaml.__version__, "sqlite3": sqlite3.sqlite_version, "read_only_projection": list(row)}, sort_keys=True))
